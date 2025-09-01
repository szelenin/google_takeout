# Cookie Authentication Guide for Google Takeout

Google Takeout links work beyond the 7-day "expiration" if you have proper authentication cookies. Here's how to use them:

## Method 1: Automatic Cookie Extraction (Recommended)

Extract cookies directly from your Chromium/Chrome browser:

```bash
# Make sure Chromium is closed
python3 extract_cookies.py

# This creates cookies.json
# Now use it with the downloader:
python google_takeout_downloader.py urls.txt --cookies cookies.json
```

## Method 2: Manual Cookie Export

### Using Browser Extension

1. Install "EditThisCookie" or "Cookie-Editor" extension in Chromium
2. Go to any Google page (e.g., google.com)
3. Click the extension icon
4. Export cookies as JSON
5. Save to `cookies.json`

### Using Developer Tools

1. Open Chromium on your Raspberry Pi
2. Go to https://takeout.google.com
3. Press `F12` to open Developer Tools
4. Go to **Application** tab → **Cookies**
5. Look for cookies from these domains:
   - `google.com`
   - `googleapis.com`
   - `googleusercontent.com`
6. Important cookies to copy:
   - `SID`
   - `HSID`
   - `SSID`
   - `APISID`
   - `SAPISID`

Create `cookies.json` with format:
```json
{
  "SID": "your_sid_value",
  "HSID": "your_hsid_value",
  "SSID": "your_ssid_value",
  "APISID": "your_apisid_value",
  "SAPISID": "your_sapisid_value"
}
```

## Method 3: Export from Chrome Download Page

Since you mentioned downloads work from Chrome's download history:

1. Open Chrome download page: `chrome://downloads/`
2. Open Developer Tools (`F12`)
3. Go to **Network** tab
4. Click "Resume" on a paused download
5. Find the request in Network tab
6. Right-click → Copy → Copy as cURL
7. Extract cookies from the cURL command

## Using Cookies with the Downloader

Once you have `cookies.json`:

```bash
# Basic usage with cookies
python google_takeout_downloader.py urls.txt --cookies cookies.json

# Full example
python google_takeout_downloader.py urls.txt \
  --cookies cookies.json \
  --output-dir /path/to/downloads \
  --max-workers 2
```

## Important Notes

1. **Keep Chromium logged in**: The cookies are tied to your Google session
2. **Don't clear browser data**: This will invalidate the cookies
3. **Update cookies if needed**: If downloads fail, re-extract cookies
4. **Session persistence**: As long as you stay logged in, cookies remain valid

## Troubleshooting

### "Sign in - Google Accounts" error
- Cookies are invalid or expired
- Re-extract cookies after logging into Google

### Permission denied accessing cookies
```bash
# On Raspberry Pi, you might need to close Chromium first
pkill chromium
python3 extract_cookies.py
```

### Finding Chromium profile
```bash
# Find your Chromium profile location
ls ~/.config/chromium/
# Usually "Default" or "Profile 1"
```

## Security Note

⚠️ **Keep your cookies file secure!** It contains authentication tokens that provide access to your Google account. Never share this file or commit it to version control.