#!/usr/bin/env bash
set -euo pipefail

# Config
WORK_DIR="$HOME/chartpipe-work"
IMAGE="ghcr.io/anyshkhdr/chartpipe:latest"
IN_FILE="NewPipeData-in.zip"
OUT_FILE="NewPipeData-out.zip"
LOG_DIR="$WORK_DIR/logs"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/sync-$(date +%Y%m%d-%H%M%S).log"

log() {
	    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
    }

    log "=== Chartpipe weekly sync starting ==="

    # 1. Verify input exists
    if [[ ! -f "$WORK_DIR/$IN_FILE" ]]; then
	        log "ERROR: $WORK_DIR/$IN_FILE not found. Skipping run."
		    exit 1
    fi

    # 2. Pull latest image
    log "Pulling latest image..."
docker pull "$IMAGE" >> "$LOG_FILE" 2>&1 || {
	    log "ERROR: docker pull failed."
    exit 1
}

# 3. Run sync
log "Running sync..."
docker run --rm \
	    -v "$WORK_DIR:/data" \
	        "$IMAGE" \
		    sync "/data/$IN_FILE" -o "/data/$OUT_FILE" >> "$LOG_FILE" 2>&1

log "Sync completed. Output: $WORK_DIR/$OUT_FILE"

# 4. Rotate old logs (keep last 30)
find "$LOG_DIR" -name "sync-*.log" -mtime +30 -delete 2>/dev/null || true

log "=== Chartpipe weekly sync done ==="
