# YouTube → Cloudinary API (Hugging Face Space)

This Space exposes a simple FastAPI endpoint that:
1. Accepts a JSON payload with a YouTube URL.
2. Downloads the video using `yt-dlp`.
3. Uploads it to Cloudinary.
4. Returns the Cloudinary link.

### Example request
```bash
curl -X POST https://YOUR_SPACE_NAME.hf.space/process \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://youtube.com/shorts/abc123"}'
