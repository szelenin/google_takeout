# Google Takeout Downloader

A robust Python script for downloading Google Takeout archives with automatic resume capability, concurrent downloads, and cookie authentication support. Perfect for Raspberry Pi and other systems with unstable network connections.

## Features

- ✅ **Cookie & Header Authentication** - Works with "expired" Google Takeout links using browser cookies and headers
- ✅ **Resume capability** - Automatically resumes interrupted downloads
- ✅ **Concurrent downloads** - Download up to 4 files simultaneously (configurable)
- ✅ **Progress tracking** - Persistent progress saved to JSON file
- ✅ **Expired link handling** - Detects and reports expired links
- ✅ **Retry logic** - Automatically retries failed downloads (up to 3 times)
- ✅ **Raspberry Pi optimized** - Minimal dependencies, works great on RPi

## Requirements

- Python 3.6+
- `requests` library (installed via requirements.txt)
- Chromium or Chrome browser (for cookie extraction)

## Complete Setup Guide

### Step 1: Clone the Repository

```bash
# Clone from GitHub
git clone https://github.com/szelenin/google_takeout.git
cd google_takeout
```

### Step 2: Setup Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies (works for both scripts)
pip install -r requirements.txt
```

### Step 3: Extract Headers and Cookies from Browser

Google Takeout links require authentication cookies and headers to work, especially after the 7-day "expiration" period. The `extract_headers.py` script automatically extracts these from your browser.

```bash
# Make sure you're logged into Google in Chromium/Chrome
# Close the browser for best results (optional but recommended)

# Extract headers and cookies (still in venv)
python extract_headers.py

# This creates two files:
# - headers.json (contains both cookies and headers for the downloader)
# - cookies_detailed.json (detailed cookie information for debugging)
```

**Advanced Usage with cURL:**
For best compatibility, you can also provide a cURL command from your browser:

```bash
# Copy a working download link as cURL from browser developer tools
python extract_headers.py --curl "curl 'https://takeout-download...' -H 'accept: text/html...' -b 'SID=...'"

# Or save cURL command to file
echo "curl 'https://...' -H '...' -b '...'" > curl_command.txt
python extract_headers.py --curl-file curl_command.txt
```

**What the header extractor does:**
1. Finds your browser's cookie database and extracts Google authentication cookies
2. Optionally parses cURL commands to extract both cookies and headers
3. Combines browser cookies with cURL headers (cURL takes precedence)
4. Saves everything in headers.json format for the downloader to use

### Step 4: Add Your Download URLs

Edit `urls.txt` and add your Google Takeout download URLs (one per line):

```bash
# Edit the file
nano urls.txt

# Or copy URLs from Chrome's download history and paste them
```

Example urls.txt:
```
https://takeout-download.usercontent.google.com/download/takeout-20250823T223815Z-1-001.zip?...
https://takeout-download.usercontent.google.com/download/takeout-20250823T223815Z-1-002.zip?...
https://takeout-download.usercontent.google.com/download/takeout-20250823T223815Z-1-003.zip?...
```

### Step 5: Run the Downloader

#### Option A: Foreground (attached to terminal)
```bash
# Run with headers (uses headers.json automatically if present)
python google_takeout_downloader.py urls.txt

# Or specify custom output directory
python google_takeout_downloader.py urls.txt --output-dir /path/to/downloads
```

#### Option B: Background (survives SSH disconnection)
```bash
# Use the background script (recommended for large downloads)
./download_background.sh urls.txt /mnt/raid1/users/sync

# With additional options
./download_background.sh urls.txt /mnt/raid1/users/sync --max-workers 2

# Monitor progress
tail -f download_YYYYMMDD_HHMMSS.log

# Stop download if needed
kill PID_NUMBER  # (shown when starting)
```

## Command-line Options

### Downloader Options

- `urls_file` - Text file containing download URLs (required)
- `--output-dir`, `-o` - Directory to save downloads (default: ./downloads)
- `--max-workers`, `-w` - Maximum concurrent downloads (default: 4)
- `--chunk-size`, `-c` - Download chunk size in bytes (default: 8192)
- `--headers` - Path to headers JSON file (optional, uses headers.json by default)

### Examples

```bash
# Basic usage (uses headers.json automatically)
python google_takeout_downloader.py urls.txt

# Custom settings for Raspberry Pi
python google_takeout_downloader.py urls.txt \
  --output-dir /mnt/usb/downloads \
  --max-workers 2 \
  --chunk-size 4096

# With custom headers file
python google_takeout_downloader.py urls.txt --headers my_headers.json
```

## How It Works

### Header and Cookie Extraction Process

1. The `extract_headers.py` script locates your browser's SQLite cookie database:
   - Linux/RPi: `~/.config/chromium/Default/Cookies`
   - macOS: `~/Library/Application Support/Google/Chrome/Default/Cookies`

2. It queries the database for Google-related cookies needed for authentication

3. Optionally parses cURL commands to extract additional headers and cookies

4. Saves both cookies and headers in JSON format that the downloader can use

### Download Process

1. **Progress Tracking**: The script saves progress to `download_progress.json`
2. **Resume Downloads**: If interrupted, it automatically resumes from where it left off
3. **Concurrent Processing**: Downloads multiple files simultaneously (configurable)
4. **Error Handling**: Automatically retries failed downloads and reports expired links

## Troubleshooting

### "Sign in - Google Accounts" HTML instead of ZIP files

**Problem**: Downloaded files are HTML login pages, not ZIP archives

**Solution**: You need to extract and use cookies and headers:
```bash
python extract_headers.py
python google_takeout_downloader.py urls.txt
```

### Cookie Extraction Fails

**Problem**: Can't find browser cookies or permission denied

**Solutions**:
```bash
# 1. Make sure browser is closed
pkill chromium

# 2. Check if you're logged into Google
# Open browser, go to google.com, verify you're logged in

# 3. Find your browser profile
ls ~/.config/chromium/
# Look for "Default" or "Profile 1"

# 4. Manual extraction (if automatic fails)
# See "Manual Cookie Extraction" section below

# 5. Use cURL extraction as fallback
# Copy download link as cURL from browser developer tools
python extract_headers.py --curl "your_curl_command_here"
```

### Network Keeps Dropping

**Solution**: Reduce concurrent downloads and chunk size:
```bash
python google_takeout_downloader.py urls.txt \
  --max-workers 1 \
  --chunk-size 2048
```

### Expired Links

**Problem**: Links show as expired even with cookies

**Solution**: 
- If it's been more than 7 days AND you've logged out of Google, you'll need new takeout links
- As long as you stay logged in, cookies should keep working beyond 7 days
- Try extracting fresh headers with cURL: Copy a working download as cURL from browser developer tools

## Manual Cookie Extraction

If automatic extraction doesn't work, you can manually extract cookies:

### Method 1: Browser Developer Tools

1. Open Chromium/Chrome
2. Go to https://takeout.google.com
3. Press `F12` to open Developer Tools
4. Go to **Application** → **Cookies** → `google.com`
5. Find and copy these cookie values:
   - `SID`
   - `HSID`
   - `SSID`
   - `APISID`
   - `SAPISID`

6. Create `headers.json` manually:
```json
{
  "cookies": {
    "SID": "paste_your_SID_value_here",
    "HSID": "paste_your_HSID_value_here",
    "SSID": "paste_your_SSID_value_here",
    "APISID": "paste_your_APISID_value_here",
    "SAPISID": "paste_your_SAPISID_value_here"
  },
  "headers": {
    "User-Agent": "Mozilla/5.0 (compatible browser string)"
  }
}
```

### Method 2: Browser Extension

1. Install "EditThisCookie" or "Cookie-Editor" extension
2. Go to any Google page
3. Click the extension icon
4. Export cookies as JSON
5. Format as headers.json with cookies and headers sections

## Tips for Raspberry Pi

### Use screen or tmux for long downloads

```bash
# Install screen
sudo apt-get install screen

# Start a new screen session
screen -S takeout

# Activate venv and run downloader
source venv/bin/activate
python google_takeout_downloader.py urls.txt

# Detach from screen: Ctrl+A then D
# Reattach later: screen -r takeout
```

### Monitor Progress

```bash
# In another terminal, watch the progress file
watch -n 2 'cat /path/to/output/download_progress.json | python3 -m json.tool | grep -E "(status|bytes_downloaded|filename)"'

# Or watch file sizes grow
watch -n 2 'ls -lh /path/to/output/*.zip'

# Check disk space
df -h

# Monitor system resources
htop
```

### Using External USB Drive

```bash
# Mount USB drive
sudo mkdir -p /mnt/usb
sudo mount /dev/sda1 /mnt/usb

# Download directly to USB
python google_takeout_downloader.py urls.txt \
  --output-dir /mnt/usb/google_takeout
```

## Files Created

- `headers.json` - Google authentication cookies and headers (from extract_headers.py)
- `cookies_detailed.json` - Detailed cookie information for debugging
- `download_background.sh` - Background downloader script (survives SSH disconnection)
- `download_YYYYMMDD_HHMMSS.log` - Download log file (when using background script)
- `downloads/` - Directory containing downloaded files
- `downloads/download_progress.json` - Progress tracking (safe to delete after completion)

## Security Note

⚠️ **Keep your headers.json file secure!** It contains authentication tokens that provide access to your Google account. 
- Never share this file
- Never commit it to version control
- Delete it after downloads complete if desired

## License

MIT License - Feel free to modify and use as needed!