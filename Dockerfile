# Use an official lightweight Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables to prevent bytecode files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed for PostgreSQL and compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first to take advantage of Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code into the container
COPY app/ /app/app/
COPY nodes/ /app/nodes/
COPY routes/ /app/routes/
COPY schema/ /app/schema/
COPY utils/ /app/utils/
COPY connector.py /app/connector.py


# Start FastAPI server using uvicorn binding dynamically to Render's $PORT (fallback to 8000)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

