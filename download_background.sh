#!/bin/bash
# Background downloader script for Google Takeout
# Usage: ./download_background.sh urls.txt /path/to/output

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <urls_file> <output_dir> [additional_args...]"
    echo "Example: $0 urls.txt /mnt/raid1/users/sync"
    echo "Example: $0 urls.txt /tmp --max-workers 2"
    exit 1
fi

URLS_FILE="$1"
OUTPUT_DIR="$2"
shift 2  # Remove first two arguments
ADDITIONAL_ARGS="$@"  # Capture remaining arguments

# Check if URLs file exists
if [ ! -f "$URLS_FILE" ]; then
    echo "Error: URLs file '$URLS_FILE' not found"
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Activate venv if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Generate log filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="download_${TIMESTAMP}.log"

echo "Starting background download..."
echo "URLs file: $URLS_FILE"
echo "Output directory: $OUTPUT_DIR"
echo "Log file: $LOG_FILE"
echo "Additional args: $ADDITIONAL_ARGS"

# Run downloader in background with nohup (unbuffered output)
nohup python -u google_takeout_downloader.py "$URLS_FILE" --output-dir "$OUTPUT_DIR" $ADDITIONAL_ARGS > "$LOG_FILE" 2>&1 &

# Get the process ID
PID=$!
echo "Download started in background with PID: $PID"
echo "Monitor progress with: tail -f $LOG_FILE"
echo "Stop download with: kill $PID"

# Show initial log output
echo ""
echo "=== Initial log output ==="
sleep 2
head -20 "$LOG_FILE" 2>/dev/null || echo "Waiting for log file to be created..."