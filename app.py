from fastapi import FastAPI, Request
import subprocess, os, glob, json
import cloudinary, cloudinary.uploader
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
import yt_dlp

app = FastAPI()

# --- Cloudinary Config ---
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# --- Google Sheets Setup ---
SERVICE_JSON = os.getenv("GOOGLE_SERVICE_JSON")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

credentials = service_account.Credentials.from_service_account_info(
    json.loads(SERVICE_JSON),
    scopes=SCOPES
)
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

@app.post("/process")
async def process_video(request: Request):
    data = await request.json()
    video_url = data.get("video_url")

    if not video_url:
        return {"error": "Missing video_url"}

    try:
        # --- Extract video info ---
        with yt_dlp.YoutubeDL({}) as ydl:
            info = ydl.extract_info(video_url, download=False)

        title = info.get("title", "video")
        description = info.get("description", "")
        thumbnail = info.get("thumbnail", "")
        tags = ",".join(info.get("tags", []))

        # --- Download video ---
        subprocess.run([
            "yt-dlp",
            "-f", "bestvideo+bestaudio",
            "--merge-output-format", "mp4",
            "-o", "%(title)s.%(ext)s",
            video_url
        ], check=True)

        files = glob.glob("*.mp4")
        if not files:
            return {"error": "Download failed, no MP4 file found."}

        output_path = files[0]

        # --- Upload to Cloudinary ---
        upload_result = cloudinary.uploader.upload(
            output_path,
            resource_type="video"
        )
        cloudinary_url = upload_result["secure_url"]

        # --- Prepare row for Google Sheets ---
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [
            timestamp,               # Timestamp
            video_url,               # YouTube Video URL
            cloudinary_url,          # Cloudinary URL
            title,                   # Title
            description,             # Description
            thumbnail,               # Thumbnail URL
            tags,                    # Tags
            "",                      # Instagram Caption (empty for now)
            "",                      # Published At (empty)
            "",                      # Creation ID (empty)
            ""                       # Error (empty)
        ]

        sheet.values().append(
            spreadsheetId=SHEET_ID,
            range="Sheet1!A1",  # adjust if your sheet has a different name
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row_data]}
        ).execute()

        # --- Cleanup ---
        os.remove(output_path)

        return {
            "cloudinary_url": cloudinary_url,
            "metadata": {
                "title": title,
                "description": description,
                "thumbnail": thumbnail,
                "tags": tags
            }
        }

    except Exception as e:
        return {"error": str(e)}
