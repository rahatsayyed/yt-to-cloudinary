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

def validate_cookies_file():
    """Validate that cookies file exists and has proper format."""
    if not os.path.exists(COOKIES_PATH):
        log_event(logging.WARNING, "COOKIES", f"Cookies file not found at {COOKIES_PATH}")
        return False
    
    try:
        with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                log_event(logging.WARNING, "COOKIES", "Cookies file is empty")
                return False
            
            lines = [l for l in content.split('\n') if l.strip() and not l.startswith('#')]
            if lines:
                first_line = lines[0]
                if '\t' not in first_line:
                    log_event(logging.ERROR, "COOKIES", "Cookies file is not in Netscape format (no tabs found)")
                    return False
        
        log_event(logging.INFO, "COOKIES", f"Cookies file validated at {COOKIES_PATH}")
        return True
    except Exception as e:
        log_event(logging.ERROR, "COOKIES", f"Error reading cookies file: {e}")
        return False

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

    has_cookies = validate_cookies_file()

    try:
        # --- Extract metadata ---
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
        }
        if has_cookies:
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

        # --- Download Video with retries and better error handling ---
        out_template = os.path.join(save_dir, f"{video_id}.%(ext)s")
        log_event(logging.INFO, "DOWNLOAD", f"Downloading {video_id} ({title})")

        download_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "outtmpl": out_template,
            "quiet": False,
            "no_warnings": False,
            "retries": 10,
            "fragment_retries": 10,
            "skip_unavailable_fragments": True,
            "keepvideo": False,
            "http_chunk_size": 10485760,  # 10MB chunks for better stability
            "extractor_retries": 3,
            "file_access_retries": 3,
            "concurrent_fragment_downloads": 1,  # Avoid overwhelming network
        }
        if has_cookies:
            download_opts["cookiefile"] = COOKIES_PATH

        with yt_dlp.YoutubeDL(download_opts) as ydl:
            ydl.download([video_url])

        # --- Find the downloaded file ---
        possible = [f for f in os.listdir(save_dir) if f.startswith(video_id + ".")]
        if not possible:
            raise FileNotFoundError(f"Downloaded file for {video_id} not found")
        mp4_files = [p for p in possible if p.lower().endswith(".mp4")]
        temp_filename = os.path.join(save_dir, mp4_files[0] if mp4_files else possible[0])

        # --- Upload to Cloudinary ---
        log_event(logging.INFO, "UPLOAD", f"Uploading file {temp_filename} to Cloudinary")
        upload_result = cloudinary.uploader.upload(
            temp_filename,
            resource_type="video",
            timeout=300,  # 5 minute timeout for large files
            chunk_size=6000000  # 6MB chunks
        )
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
        log_event(logging.INFO, "SUCCESS", f"{title} → {cloud_url}")
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
    has_cookies = validate_cookies_file()
    
    for category, channels in CHANNELS.items():
        ensure_sheet_exists(category)
        existing_urls = get_existing_urls(category)

        for channel in channels:
            log_event(logging.INFO, "AUTO", f"Checking channel {channel} ({category})")
            try:
                ydl_opts = {
                    "extract_flat": "in_playlist",
                    "playlistend": 5,
                    "quiet": True,
                    "extractor_retries": 3,
                }
                if has_cookies:
                    ydl_opts["cookiefile"] = COOKIES_PATH

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Try different channel URL formats
                    channel_urls = [
                        f"https://www.youtube.com/@{channel}/shorts",
                        f"https://www.youtube.com/channel/{channel}/shorts",
                        f"https://www.youtube.com/@{channel}",
                        f"https://www.youtube.com/channel/{channel}",
                    ]
                    
                    playlist_info = None
                    for channel_url in channel_urls:
                        try:
                            playlist_info = ydl.extract_info(channel_url, download=False)
                            if playlist_info:
                                break
                        except Exception:
                            continue
                    
                    if not playlist_info:
                        log_event(logging.WARNING, "AUTO", f"Could not fetch playlist for {channel}")
                        continue

                    entries = playlist_info.get("entries", [])
                    video_ids = [e.get("id") for e in entries if e.get("id")][:5]

                for vid in video_ids:
                    url = f"https://www.youtube.com/watch?v={vid}"
                    if url not in existing_urls:
                        log_event(logging.INFO, "AUTO", f"New video found: {url}")
                        process_video(url, category)
                        time.sleep(5)  # Increased delay between videos
                    else:
                        log_event(logging.DEBUG, "AUTO", f"Already logged: {url}")
                        
            except Exception as e:
                log_event(logging.ERROR, "AUTO", f"Failed fetching from {channel}: {e}")

    log_event(logging.INFO, "AUTO", "Periodic fetch cycle complete")

# === Scheduler Thread ===
scheduler_started = False

def run_scheduler():
    global scheduler_started
    if scheduler_started:
        return
    scheduler_started = True
    
    log_event(logging.INFO, "SCHEDULER", "Starting scheduler thread")
    validate_cookies_file()

    # initial run at startup
    log_event(logging.INFO, "SCHEDULER", "Initial run triggered at startup")
    fetch_new_videos()

    # schedule recurring runs
    schedule.every().hour.at(":00").do(fetch_new_videos)
    schedule.every().hour.at(":30").do(fetch_new_videos)

    while True:
        schedule.run_pending()
        time.sleep(60)

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

@app.get("/validate-cookies")
def check_cookies():
    """Endpoint to validate cookies file format"""
    is_valid = validate_cookies_file()
    return {"valid": is_valid, "path": COOKIES_PATH}

@app.on_event("startup")
async def startup_event():
    """Start scheduler on FastAPI startup"""
    threading.Thread(target=run_scheduler, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    log_event(logging.INFO, "SYSTEM", "Launching FastAPI server with scheduler")
    uvicorn.run("app:app", host="0.0.0.0", port=8000)