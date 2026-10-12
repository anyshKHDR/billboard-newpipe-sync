FROM python:3.12-slim

WORKDIR /app

# Install Python deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the package
COPY chartpipe/ ./chartpipe/
COPY pyproject.toml ./

# Data lives on a mounted volume, not in the image
ENV CHARTPIPE_DATA=/data
VOLUME ["/data"]

# Default entrypoint — override args at run time
ENTRYPOINT ["python", "-m", "chartpipe"]
CMD ["--help"]
