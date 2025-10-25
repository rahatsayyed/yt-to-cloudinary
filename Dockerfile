# Base image
FROM python:3.10-slim

# Install yt-dlp dependencies
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Copy files
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Expose FastAPI port
EXPOSE 7860

# Start the API
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
