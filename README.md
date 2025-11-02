# YouTube Shorts to Instagram Reels Automation

Automated system to download YouTube Shorts from specified channels, upload them to Cloudinary, and track them in Google Sheets for Instagram posting.

## Features

- ✅ Automatic monitoring of YouTube channels for new Shorts
- ✅ Downloads only Instagram-compatible videos (3-90 seconds)
- ✅ Uploads to Cloudinary for storage and delivery
- ✅ Tracks all videos in Google Sheets with metadata
- ✅ Automatic duplicate detection
- ✅ Scheduled checks every 30 minutes
- ✅ Cookie support for age-restricted/private content
- ✅ Manual processing endpoint
- ✅ Comprehensive logging

---

## Prerequisites

### Required Software
- Python 3.8 or higher
- pip (Python package manager)
- yt-dlp (latest version)

### Required Accounts
1. **Google Cloud Account** (for Google Sheets API)
2. **Cloudinary Account** (for video storage)
3. **YouTube Account** (optional, for cookies if accessing restricted content)

---

## Installation

### 1. Clone or Download the Repository

```bash
git clone <your-repo-url>
cd youtube-automation
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt:**
```
fastapi==0.104.1
uvicorn==0.24.0
yt-dlp>=2024.10.22
python-dotenv==1.0.0
google-auth==2.23.4
google-auth-oauthlib==1.1.0
google-auth-httplib2==0.1.1
google-api-python-client==2.108.0
cloudinary==1.36.0
schedule==1.2.0
```

### 3. Update yt-dlp to Latest Version

```bash
pip install --upgrade yt-dlp
# OR
yt-dlp -U
```

### 4. Create Required Directories

```bash
mkdir -p videos logs utils
```

---

## Configuration

### 1. Google Sheets API Setup

#### Step 1: Create a Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Click "Select Project"

#### Step 2: Enable Google Sheets API
1. Go to **APIs & Services** > **Library**
2. Search for "Google Sheets API"
3. Click **Enable**

#### Step 3: Create Service Account
1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **Service Account**
3. Fill in details:
   - Service account name: `youtube-automation`
   - Service account ID: (auto-generated)
   - Click **Create and Continue**
4. Grant role: **Editor** (or specific Sheets permissions)
5. Click **Done**

#### Step 4: Generate Service Account Key
1. Click on the created service account
2. Go to **Keys** tab
3. Click **Add Key** > **Create New Key**
4. Choose **JSON** format
5. Download the JSON file
6. **Copy the entire JSON content** (you'll need it for `.env`)

#### Step 5: Create Google Sheet
1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new spreadsheet
3. Name it (e.g., "YouTube Automation Tracker")
4. Copy the **Sheet ID** from URL:
   ```
   https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit
   ```
5. **Share the sheet** with the service account email:
   - Click **Share** button
   - Add the email from JSON: `your-service-account@project-id.iam.gserviceaccount.com`
   - Give **Editor** access

---

### 2. Cloudinary Setup

#### Step 1: Create Cloudinary Account
1. Go to [Cloudinary](https://cloudinary.com/)
2. Sign up for free account
3. Verify email

#### Step 2: Get API Credentials
1. Go to **Dashboard**
2. Copy the following from "Account Details":
   - **Cloud Name**
   - **API Key**
   - **API Secret**

---

### 3. YouTube Cookies (Optional but Recommended)

Cookies are needed for:
- Age-restricted videos
- Private/unlisted videos
- Better reliability and fewer rate limits

#### Option A: Using Browser Extension (Recommended)

1. Install **"Get cookies.txt LOCALLY"** extension:
   - [Chrome/Edge](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

2. Sign in to YouTube in your browser

3. Go to [youtube.com](https://youtube.com)

4. Click the extension icon

5. Click **"Export"** or **"Download"**

6. Save file as `cookies.txt`

7. Move to project: `./utils/cookies.txt`

#### Option B: Using yt-dlp (Alternative)

```bash
# Extract cookies from Chrome
yt-dlp --cookies-from-browser chrome --cookies ./utils/cookies.txt "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Or from Firefox
yt-dlp --cookies-from-browser firefox --cookies ./utils/cookies.txt "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

#### Cookie File Format Validation

The file must be in **Netscape HTTP Cookie File format**:
```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	1234567890	cookie_name	cookie_value
```

**Important:**
- Must use **TABS** (not spaces) between fields
- Must start with `.youtube.com`
- First line should be comment: `# Netscape HTTP Cookie File`

---

### 4. Channel Configuration

#### Finding YouTube Channel IDs

**Method 1: From Channel URL**
- Channel URL: `https://www.youtube.com/@username`
- Use: `@username`

**Method 2: Channel ID**
- Channel URL: `https://www.youtube.com/channel/UC...`
- Use: `UC...` (the ID part)

**Method 3: View Page Source**
1. Go to channel page
2. Right-click > View Page Source
3. Search for `"channelId"`
4. Copy the ID (starts with `UC`)

#### Creating CHANNELS_JSON

Create a JSON object with categories and channel IDs:

```json
{
  "motivational": ["UC7AyUr6ra_E_IJQuaQoI8kw", "@motivationaldaily"],
  "fitness": ["@fitnesschannel1", "@fitnesschannel2"],
  "cooking": ["UC1234567890abcdef", "@cookingwithchef"]
}
```

**Format:**
- Keys = Category names (will become sheet tab names)
- Values = Arrays of channel IDs or @usernames
- Can mix channel IDs and @usernames

---

### 5. Create .env File

Create a `.env` file in the project root:

```env
# Google Sheets Configuration
GOOGLE_SERVICE_JSON={"type":"service_account","project_id":"your-project","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...@....iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"..."}

GOOGLE_SHEET_ID=your_google_sheet_id_here

# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Channels Configuration (JSON format)
CHANNELS_JSON={"motivational":["UC7AyUr6ra_E_IJQuaQoI8kw"],"fitness":["@fitnesschannel"]}
```

**Important Notes:**
- `GOOGLE_SERVICE_JSON`: Paste entire JSON from downloaded service account key (as single line)
- `GOOGLE_SHEET_ID`: Copy from Sheet URL
- `CHANNELS_JSON`: Must be valid JSON (use double quotes)

---

## Project Structure

```
youtube-automation/
├── app.py                  # Main application
├── .env                    # Environment variables (create this)
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── utils/
│   └── cookies.txt        # YouTube cookies (optional)
├── videos/                # Downloaded videos (auto-created)
│   ├── motivational/
│   ├── fitness/
│   └── manual/
└── logs/
    └── app.log           # Application logs
```

---

## Usage

### Starting the Application

```bash
python app.py
```

The application will:
1. Start FastAPI server on `http://0.0.0.0:8000`
2. Validate cookies file (if exists)
3. Run initial channel check immediately
4. Schedule automatic checks every 30 minutes (at :00 and :30)

### API Endpoints

#### 1. Health Check
```bash
GET http://localhost:8000/
```
**Response:**
```json
{
  "message": "YouTube Automation API running"
}
```

#### 2. Manual Video Processing
```bash
GET http://localhost:8000/process/https://www.youtube.com/watch?v=VIDEO_ID
```
**Response:**
```json
{
  "status": "success",
  "url": "https://res.cloudinary.com/..."
}
```

#### 3. Validate Cookies
```bash
GET http://localhost:8000/validate-cookies
```
**Response:**
```json
{
  "valid": true,
  "path": "./utils/cookies.txt"
}
```

---

## Google Sheets Structure

Each category gets its own sheet tab with these columns:

| Column | Description | Filled By |
|--------|-------------|-----------|
| **Timestamp** | When video was downloaded | Script |
| **YouTube URL** | Original YouTube video link | Script |
| **Cloudinary URL** | Uploaded video CDN link | Script |
| **Title** | Video title from YouTube | Script |
| **Description** | Video description | Script |
| **Thumbnail** | Thumbnail image URL | Script |
| **Tags** | Video tags (comma-separated) | Script |
| **Instagram Caption** | Caption for Instagram post | **Manual** |
| **Published At (IG)** | When posted to Instagram | **Manual** |
| **Creation ID** | Instagram API response ID | **Manual/API** |
| **Error** | Error message if failed | Script |

---

## Video Requirements

The script only downloads videos that meet **Instagram Reels** specifications:

- ✅ **Duration**: 3-90 seconds
- ✅ **Format**: MP4
- ✅ **Aspect Ratio**: Automatically handled
- ❌ Videos longer than 90 seconds are **skipped**
- ❌ Videos shorter than 3 seconds are **skipped**

---

## Automation Schedule

The script automatically checks for new videos:
- **Every hour at :00** (e.g., 1:00 PM, 2:00 PM)
- **Every hour at :30** (e.g., 1:30 PM, 2:30 PM)
- **Initial run** when the script starts

You can modify the schedule in `app.py`:
```python
schedule.every().hour.at(":00").do(fetch_new_videos)
schedule.every().hour.at(":30").do(fetch_new_videos)
```

---

## Troubleshooting

### 1. "nsig extraction failed" Warnings

**Problem:** yt-dlp is outdated

**Solution:**
```bash
pip install --upgrade yt-dlp
# OR
yt-dlp -U
```

### 2. "HTTP Error 404: Not Found" for Channel

**Problem:** Invalid channel ID or format

**Solutions:**
- Try `@username` instead of channel ID
- Try full channel ID (starts with `UC`)
- Verify channel URL is accessible
- Add `/shorts` to the URL in code

### 3. "Unable to rename file" / Fragment Errors

**Problem:** Network instability

**Solutions:**
- Check internet connection
- The script has 10 retries built-in
- Will skip unavailable fragments
- Try again with better connection

### 4. "Cookies file is not in Netscape format"

**Problem:** Wrong cookie file format

**Solutions:**
- Re-export cookies using browser extension
- Ensure file uses TABS, not spaces
- Use `yt-dlp --cookies-from-browser` method

### 5. Google Sheets Permission Denied

**Problem:** Service account doesn't have access

**Solution:**
- Share the sheet with service account email
- Give "Editor" permissions
- Email is in the JSON: `...@....iam.gserviceaccount.com`

### 6. Cloudinary Upload Fails

**Problem:** File too large or network timeout

**Solutions:**
- Check video file size (Cloudinary free tier has limits)
- Increase timeout in code
- Check Cloudinary account quota

---

## Logs

### Log Files
- Location: `./logs/app.log`
- Includes: Timestamps, log levels, context, messages
- Rotates: Appends continuously (manage manually)

### Log Levels
- `INFO`: Normal operations
- `WARNING`: Non-critical issues (e.g., video too long)
- `ERROR`: Failed operations

### View Real-time Logs
```bash
# Linux/Mac
tail -f logs/app.log

# Windows
Get-Content logs/app.log -Wait
```

---

## Production Deployment

### Using systemd (Linux)

Create `/etc/systemd/system/youtube-automation.service`:

```ini
[Unit]
Description=YouTube to Instagram Automation
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/youtube-automation
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable youtube-automation
sudo systemctl start youtube-automation
sudo systemctl status youtube-automation
```

### Using Docker

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
```

**Build and Run:**
```bash
docker build -t youtube-automation .
docker run -d -p 8000:8000 --name yt-automation \
  -v $(pwd)/videos:/app/videos \
  -v $(pwd)/logs:/app/logs \
  --env-file .env \
  youtube-automation
```

---

## Security Best Practices

1. **Never commit `.env` file** to version control
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Protect cookies.txt**
   ```bash
   chmod 600 utils/cookies.txt
   ```

3. **Limit Google Service Account permissions**
   - Only give access to specific sheet
   - Don't use personal account

4. **Rotate Cloudinary credentials** periodically

5. **Monitor logs** for unauthorized access attempts

---

## Maintenance

### Weekly Tasks
- Check logs for errors: `tail -100 logs/app.log`
- Verify script is running: `curl http://localhost:8000/`
- Update yt-dlp: `pip install --upgrade yt-dlp`

### Monthly Tasks
- Review Google Sheets for duplicates
- Check Cloudinary storage usage
- Update cookies.txt if expired
- Review and clean up old videos

### Quarterly Tasks
- Update all Python dependencies
- Review and optimize channel list
- Backup Google Sheets data

---

## FAQ

**Q: How many channels can I monitor?**
A: Unlimited, but consider API rate limits. Recommended: 10-20 channels per category.

**Q: Will it download duplicates?**
A: No, it checks existing URLs in the sheet before downloading.

**Q: Can I run this 24/7?**
A: Yes, designed for continuous operation. Use systemd or Docker for reliability.

**Q: What if YouTube changes their API?**
A: Keep yt-dlp updated. It's actively maintained for YouTube changes.

**Q: How much does this cost?**
A: Free tier limits:
- Google Sheets API: 100 requests/100 seconds
- Cloudinary Free: 25GB storage, 25GB bandwidth/month
- YouTube: No API needed (scraping via yt-dlp)

**Q: Can I use this commercially?**
A: Check YouTube's ToS and copyright laws. This tool is for automation, not piracy.

---

## Contributing

Issues and pull requests are welcome!

---

## License

MIT License - Use at your own risk. Ensure compliance with YouTube's Terms of Service.
