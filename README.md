# Google Takeout Downloader

A robust Python script for downloading Google Takeout archives with automatic resume capability and concurrent downloads. Perfect for Raspberry Pi and other systems with unstable network connections.

## Features

- ✅ **Resume capability** - Automatically resumes interrupted downloads
- ✅ **Concurrent downloads** - Download up to 4 files simultaneously (configurable)
- ✅ **Progress tracking** - Persistent progress saved to JSON file
- ✅ **Expired link detection** - Gracefully handles expired Google Takeout links
- ✅ **Retry logic** - Automatically retries failed downloads (up to 3 times)
- ✅ **Raspberry Pi optimized** - Minimal dependencies, works great on RPi

## Quick Setup for Raspberry Pi

```bash
# Clone or copy the files to your Raspberry Pi
# Then run the setup script:
chmod +x setup_raspberry_pi.sh
./setup_raspberry_pi.sh
```

## Manual Installation

### Requirements
- Python 3.6+
- `requests` library

### Install Dependencies

```bash
# Install pip if not already installed
sudo apt-get update
sudo apt-get install python3-pip

# Install required Python package
pip3 install -r requirements.txt

# Or directly:
pip3 install requests
```

## Usage

### 1. Prepare your URLs

Add your Google Takeout download URLs to `urls.txt` (one URL per line):

```
https://takeout-download.usercontent.google.com/download/takeout-20250823T223815Z-1-001.zip?...
https://takeout-download.usercontent.google.com/download/takeout-20250823T223815Z-1-002.zip?...
https://takeout-download.usercontent.google.com/download/takeout-20250823T223815Z-1-003.zip?...
```

### 2. Run the downloader

```bash
# Basic usage
python3 google_takeout_downloader.py urls.txt

# Specify output directory
python3 google_takeout_downloader.py urls.txt --output-dir /path/to/downloads

# Limit concurrent downloads (default is 4)
python3 google_takeout_downloader.py urls.txt --max-workers 2

# Custom chunk size for slower connections (default 8192 bytes)
python3 google_takeout_downloader.py urls.txt --chunk-size 4096
```

### Command-line Options

- `urls_file` - Text file containing download URLs (required)
- `--output-dir`, `-o` - Directory to save downloads (default: ./downloads)
- `--max-workers`, `-w` - Maximum concurrent downloads (default: 4)
- `--chunk-size`, `-c` - Download chunk size in bytes (default: 8192)

## How It Works

1. **Progress Tracking**: The script saves progress to `download_progress.json` in the output directory
2. **Resume Downloads**: If a download is interrupted, the script automatically resumes from where it left off
3. **Concurrent Processing**: Downloads multiple files simultaneously for faster completion
4. **Error Handling**: Automatically retries failed downloads and reports expired links

## Tips for Raspberry Pi

1. **Use screen or tmux** to keep the download running even if SSH disconnects:
   ```bash
   screen -S takeout
   python3 google_takeout_downloader.py urls.txt
   # Press Ctrl+A then D to detach
   # Reattach with: screen -r takeout
   ```

2. **Monitor system resources**:
   ```bash
   # In another terminal
   htop
   ```

3. **Check download progress**:
   ```bash
   # View the progress file
   cat downloads/download_progress.json | python3 -m json.tool
   ```

4. **For very slow connections**, reduce workers and chunk size:
   ```bash
   python3 google_takeout_downloader.py urls.txt -w 2 -c 4096
   ```

## Troubleshooting

### Network keeps dropping
- Reduce `--max-workers` to 1 or 2
- Decrease `--chunk-size` to 4096 or 2048
- The script will automatically resume where it left off

### Links expired
- Google Takeout links expire after 7 days
- The script will mark expired links and continue with others
- You'll need to generate new takeout archives for expired links

### Out of disk space
- Check available space: `df -h`
- Google Takeout files can be very large (10-50GB each)
- Consider using an external USB drive on Raspberry Pi

## Files Created

- `downloads/` - Directory containing downloaded files
- `downloads/download_progress.json` - Progress tracking file (safe to delete after all downloads complete)

## Getting URLs from Chrome

1. Open Chrome's download page (chrome://downloads/)
2. Copy the download links for your Google Takeout files
3. Paste them into `urls.txt`

## License

MIT License - Feel free to modify and use as needed!