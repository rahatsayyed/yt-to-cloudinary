---
title: YouTube Shorts to Cloudinary + Google Sheets
emoji: 🎬
colorFrom: "red"
colorTo: "blue"
sdk: docker
sdk_version: "1.0.0"
app_file: app.py
pinned: false
---

# YouTube Shorts Upload Automation

This FastAPI app automates the following workflow:

1. Downloads a YouTube Short video using `yt-dlp`.
2. Uploads the video to **Cloudinary**.
3. Stores video metadata and Cloudinary URL in a **Google Sheet** for tracking and future Instagram posting.

---

## Features

- Downloads the best video + audio and merges into MP4.
- Handles YouTube metadata: title, description, thumbnail, tags, etc.
- Cloudinary upload for video hosting.
- Stores metadata in a Google Sheet (Timestamp, YouTube URL, Cloudinary URL, Title, Description, Thumbnail URL, Tags, Instagram Caption, Published At, Creation ID, Error).

---

## Required Environment Variables

Set these as **Secrets** in your Hugging Face Space:

| Name | Description |
|------|-------------|
| `CLOUDINARY_CLOUD_NAME` | Your Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Your Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Your Cloudinary API secret |
| `GOOGLE_SERVICE_JSON` | Your Google service account JSON (single-line) |
| `GOOGLE_SHEET_ID` | Google Sheet ID where video metadata will be stored |

> **Notes:**
> - `GOOGLE_SERVICE_JSON` can be obtained from Google Cloud Console under **Service Accounts → Keys → JSON**.
> - Make sure to convert it to a single line if using HF Spaces Secrets.

---

## Installation / Deployment

This app is designed for **Hugging Face Spaces**:

1. Create a new Space → choose **“Custom”** for a FastAPI backend.
2. Clone the Space repo locally:

```bash
git clone https://huggingface.co/spaces/<username>/<space_name>
cd <space_name>
