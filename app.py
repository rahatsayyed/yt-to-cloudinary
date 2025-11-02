from fastapi import FastAPI
from google.oauth2 import service_account
from googleapiclient.discovery import build
import cloudinary, cloudinary.uploader
import yt_dlp
import subprocess, os, json, time, threading, schedule, logging
from datetime import datetime
from dotenv import load_dotenv
import warnings

warnings.filterwarnings("ignore", message="file_cache is only supported")

# --- Load environment ---
load_dotenv()
app = FastAPI()

# === Logging Setup ===
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("yt-auto")

# --- Cloudinary Config ---
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# --- Google Sheets Config ---
SERVICE_JSON = os.getenv("GOOGLE_SERVICE_JSON")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = service_account.Credentials.from_service_account_info(json.loads(SERVICE_JSON), scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# --- Channels per Category ---
CHANNELS = json.loads(os.getenv("CHANNELS_JSON", "{}"))

# --- Constants ---
COOKIES_PATH = "./utils/cookies.txt"
VIDEO_ROOT = "./videos"

# === Helper Functions ===
def log_event(level, context, message):
    log.log(level, f"[{context}] {message}")

def ensure_sheet_exists(sheet_name):
    """Ensure tab exists and header row is set."""
    try:
        meta = sheet.get(spreadsheetId=SHEET_ID).execute()
        existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
        headers = [["Timestamp","YouTube URL","Cloudinary URL","Title","Description",
                    "Thumbnail","Tags","Instagram Caption","Published At","Creation ID","Error"]]

        if sheet_name not in existing:
            sheet.batchUpdate(
                spreadsheetId=SHEET_ID,
                body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}
            ).execute()
            time.sleep(1)
            log_event(logging.INFO, "SHEET", f"Created new sheet '{sheet_name}'")

        result = sheet.values().get(spreadsheetId=SHEET_ID, range=f"{sheet_name}!A1:K1").execute()
        current = result.get("values", [])
        if not current or len(current[0]) < len(headers[0]):
            sheet.values().update(
                spreadsheetId=SHEET_ID,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                body={"values": headers}
            ).execute()
            log_event(logging.INFO, "SHEET", f"Ensured headers for '{sheet_name}'")

    except Exception as e:
        log_event(logging.ERROR, "SHEET", f"Error ensuring sheet '{sheet_name}': {e}")

def get_existing_urls(sheet_name):
    try:
        result = sheet.values().get(spreadsheetId=SHEET_ID, range=f"{sheet_name}!B2:B").execute()
        return {r[0] for r in result.get("values", []) if r}
    except Exception:
        return set()

def append_row(sheet_name, row):
    try:
        while len(row) < 11:
            row.append("")
        sheet.values().append(
            spreadsheetId=SHEET_ID,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]}
        ).execute()
    except Exception as e:
        log_event(logging.ERROR, "SHEET", f"Failed to append row to {sheet_name}: {e}")

# === Core Processing Logic ===
def process_video(video_url: str, category: str = "manual"):
    """Download, upload to Cloudinary, and log to Google Sheet."""
    log_event(logging.INFO, "PROCESS", f"{category.upper()} processing started for {video_url}")
    ensure_sheet_exists(category)

    temp_filename = None
    save_dir = os.path.join(VIDEO_ROOT, category)
    os.makedirs(save_dir, exist_ok=True)

    try:
        # --- Extract metadata ---
        ydl_opts = {"quiet": True}
        if os.path.exists(COOKIES_PATH):
            ydl_opts["cookiefile"] = COOKIES_PATH

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        video_id = info.get("id")
        title = info.get("title", "video")
        description = info.get("description", "")
        thumbnail = info.get("thumbnail", "")
        tags = ",".join(info.get("tags", []))
        published_at = info.get("upload_date", "")
        duration = info.get("duration", 0)

        # --- Skip non-Shorts ---
        if duration > 65:
            raise RuntimeError(f"Video too long ({duration}s) — not a Short")

        # --- Download Video ---
        out_template = os.path.join(save_dir, f"{video_id}.%(ext)s")
        log_event(logging.INFO, "DOWNLOAD", f"Downloading {video_id} ({title}) to {out_template}")

        cmd = [
            "yt-dlp",
            "-f", "bestvideo+bestaudio",
            "--merge-output-format", "mp4",
            "-o", out_template
        ]
        if os.path.exists(COOKIES_PATH):
            cmd += ["--cookies", COOKIES_PATH]
        cmd.append(video_url)

        subprocess.run(cmd, check=True)

        # --- Find the downloaded file ---
        possible = [f for f in os.listdir(save_dir) if f.startswith(video_id + ".")]
        if not possible:
            raise FileNotFoundError(f"Downloaded file for {video_id} not found")
        mp4_files = [p for p in possible if p.lower().endswith(".mp4")]
        temp_filename = os.path.join(save_dir, mp4_files[0] if mp4_files else possible[0])

        # --- Upload to Cloudinary ---
        log_event(logging.INFO, "UPLOAD", f"Uploading file {temp_filename} to Cloudinary")
        upload_result = cloudinary.uploader.upload(temp_filename, resource_type="video")
        cloud_url = upload_result.get("secure_url")

        # --- Cleanup ---
        try:
            os.remove(temp_filename)
            log_event(logging.INFO, "CLEANUP", f"Deleted local file {temp_filename}")
        except Exception as e_rm:
            log_event(logging.WARNING, "CLEANUP", f"Failed to remove temp file {temp_filename}: {e_rm}")

        # --- Append to Sheet ---
        row = [
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            video_url, cloud_url, title, description, thumbnail, tags, "",
            published_at, "", ""
        ]
        append_row(category, row)
        log_event(logging.INFO, "UPLOAD", f"Success: {title} → {cloud_url}")
        return {"status": "success", "url": cloud_url}

    except Exception as e:
        log_event(logging.ERROR, "ERROR", f"Failed {video_url}: {e}")
        append_row(category, [
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            video_url, "", "", "", "", "", "", "", "", str(e)
        ])
        try:
            if temp_filename and os.path.exists(temp_filename):
                os.remove(temp_filename)
        except Exception:
            pass
        return {"error": str(e)}

# === Periodic Scheduler ===
def fetch_new_videos():
    log_event(logging.INFO, "AUTO", "Starting periodic fetch cycle")
    for category, channels in CHANNELS.items():
        ensure_sheet_exists(category)
        existing_urls = get_existing_urls(category)

        for channel in channels:
            log_event(logging.INFO, "AUTO", f"Checking channel {channel} ({category})")
            try:
                cmd = [
                    "yt-dlp",
                    f"https://www.youtube.com/channel/{channel}",
                    "--flat-playlist", "--get-id", "--playlist-end", "5"
                ]
                if os.path.exists(COOKIES_PATH):
                    cmd += ["--cookies", COOKIES_PATH]

                output = subprocess.check_output(cmd, text=True)
                video_ids = [v.strip() for v in output.splitlines() if v.strip()]

                for vid in video_ids:
                    url = f"https://www.youtube.com/watch?v={vid}"
                    if url not in existing_urls:
                        log_event(logging.INFO, "AUTO", f"New video found: {url}")
                        process_video(url, category)
                        time.sleep(3)
                    else:
                        log_event(logging.DEBUG, "AUTO", f"Already logged: {url}")
            except Exception as e:
                log_event(logging.ERROR, "AUTO", f"Failed fetching from {channel}: {e}")

    log_event(logging.INFO, "AUTO", "Periodic fetch cycle complete")

# === Scheduler Thread ===
def run_scheduler():
    log_event(logging.INFO, "SCHEDULER", "Starting scheduler thread")

    # initial run at startup
    log_event(logging.INFO, "SCHEDULER", "Initial run triggered at startup")
    fetch_new_videos()

    # schedule recurring runs
    schedule.every().hour.at(":00").do(fetch_new_videos)
    schedule.every().hour.at(":30").do(fetch_new_videos)

    while True:
        schedule.run_pending()
        time.sleep(60)

# start scheduler thread
threading.Thread(target=run_scheduler, daemon=True).start()

# === FastAPI Routes ===
@app.get("/")
def home():
    return {"message": "YouTube Automation API running"}

@app.get("/process/{url:path}")
def manual_process(url: str):
    video_url = url if url.startswith("http") else f"https://{url}"
    log_event(logging.INFO, "MANUAL", f"Manual trigger for {video_url}")
    result = process_video(video_url, "manual")
    log_event(logging.INFO, "MANUAL", f"Manual processing done for {video_url}")
    return result

if __name__ == "__main__":
    import uvicorn
    log_event(logging.INFO, "SYSTEM", "Launching FastAPI server with scheduler")
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
