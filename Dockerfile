FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY run_pipeline.py .
COPY cloud_run_server.py .
COPY modal_whisperx.py .
COPY modal_whisperx_v2.py .

# Create temp directory
RUN mkdir -p temp logs Transcripts

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080

# Run the HTTP wrapper (which runs pipeline in background)
CMD ["python", "cloud_run_server.py"]
