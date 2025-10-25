from fastapi import FastAPI, Request
import subprocess, os, glob
import cloudinary, cloudinary.uploader
import yt_dlp

app = FastAPI()

# --- Cloudinary Config ---
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

@app.post("/process")
async def process_video(request: Request):
    data = await request.json()
    video_url = data.get("video_url")

    if not video_url:
        return {"error": "Missing video_url"}

    try:
        # --- Extract video info using yt-dlp ---
        ydl_opts_info = {}
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(video_url, download=False)

        video_title = info.get("title", "video")
        video_description = info.get("description", "")
        video_uploader = info.get("uploader", "")
        video_uploader_url = info.get("uploader_url", "")
        video_webpage_url = info.get("webpage_url", "")
        video_duration = info.get("duration", 0)
        video_thumbnail = info.get("thumbnail", "")

        # --- Download using yt-dlp ---
        subprocess.run([
            "yt-dlp",
            "-f", "bestvideo+bestaudio",
            "--merge-output-format", "mp4",
            "-o", "%(title)s.%(ext)s",
            video_url
        ], check=True)

        # --- Find the downloaded file ---
        files = glob.glob("*.mp4")
        if not files:
            return {"error": "Download failed, no MP4 file found."}

        output_path = files[0]

        # --- Upload to Cloudinary using custom_metadata ---
        upload_result = cloudinary.uploader.upload(
            output_path,
            resource_type="video",
            custom_metadata={
                "original_title": video_title,
                "caption": video_description,
                "uploader": video_uploader,
                "uploader_url": video_uploader_url,
                "original_video_url": video_webpage_url,
                "thumbnail": video_thumbnail,
                "duration": str(video_duration)  # must be string
            }
        )

        # --- Clean up local file ---
        os.remove(output_path)

        return {
            "cloudinary_url": upload_result["secure_url"],
            "file_name": os.path.basename(output_path),
            "metadata": {
                "original_title": video_title,
                "caption": video_description,
                "uploader": video_uploader,
                "uploader_url": video_uploader_url,
                "original_video_url": video_webpage_url,
                "thumbnail": video_thumbnail,
                "duration": video_duration
            }
        }

    except subprocess.CalledProcessError as e:
        return {"error": f"Download failed: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}
