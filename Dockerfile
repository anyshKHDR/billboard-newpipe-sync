FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY chartpipe/ ./chartpipe/
COPY pyproject.toml ./

ENV CHARTPIPE_DATA=/data
ENV PYTHONUNBUFFERED=1

VOLUME ["/data"]

ENTRYPOINT ["python", "-m", "chartpipe"]
CMD ["--help"]
