FROM python:3.10-slim

# Install system packages
RUN apt-get update && apt-get install -y ffmpeg git && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY transcribe_all.py .

# Create input/output folders
RUN mkdir -p input output

CMD ["python", "transcribe_all.py"] 