#!/usr/bin/env python3
"""
Extract cookies from Chromium/Chrome for Google Takeout downloads
Works on Raspberry Pi and other Linux systems
"""

import sqlite3
import json
import os
import sys
import shutil
from pathlib import Path
import tempfile

def find_chromium_cookies_db():
    """Find Chromium/Chrome cookies database"""
    possible_paths = [
        # Chromium on Linux/Raspberry Pi
        Path.home() / ".config/chromium/Default/Cookies",
        Path.home() / ".config/chromium/Profile 1/Cookies",
        # Chrome on Linux
        Path.home() / ".config/google-chrome/Default/Cookies",
        Path.home() / ".config/google-chrome/Profile 1/Cookies",
        # Chrome on macOS
        Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies",
        # Chromium on macOS
        Path.home() / "Library/Application Support/Chromium/Default/Cookies",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None

def extract_google_cookies(cookies_db_path):
    """Extract Google-related cookies from Chrome/Chromium database"""
    # Create a temporary copy of the database (Chrome might have it locked)
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        shutil.copy2(cookies_db_path, tmp_path)
        
        # Connect to the copied database
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()
        
        # Query for Google-related cookies (including all subdomains)
        query = """
        SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly
        FROM cookies
        WHERE host_key LIKE '%google.com%' 
           OR host_key LIKE '%googleapis.com%'
           OR host_key LIKE '%googleusercontent.com%'
           OR host_key LIKE '%usercontent.google.com%'
           OR host_key LIKE '%.google.com'
           OR host_key = 'google.com'
        """
        
        cursor.execute(query)
        cookies = cursor.fetchall()
        
        # Convert to dictionary format
        cookie_dict = {}
        cookie_list = []
        
        for cookie in cookies:
            host, name, value, path, expires, secure, httponly = cookie
            
            # Simple key-value format
            cookie_dict[name] = value
            
            # Detailed format (for Cookie-Editor extension format)
            cookie_list.append({
                "domain": host,
                "name": name,
                "value": value,
                "path": path,
                "secure": bool(secure),
                "httpOnly": bool(httponly)
            })
        
        conn.close()
        
        return cookie_dict, cookie_list
        
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def main():
    # Find cookies database
    cookies_db = find_chromium_cookies_db()
    
    if not cookies_db:
        print("Error: Could not find Chromium/Chrome cookies database")
        print("Make sure Chromium/Chrome is installed and you've logged into Google")
        sys.exit(1)
    
    print(f"Found cookies database: {cookies_db}")
    
    try:
        # Extract cookies
        simple_cookies, detailed_cookies = extract_google_cookies(cookies_db)
        
        if not simple_cookies:
            print("No Google cookies found. Make sure you're logged into Google in Chromium/Chrome")
            sys.exit(1)
        
        # Save simple format (key-value pairs)
        with open("cookies.json", "w") as f:
            json.dump(simple_cookies, f, indent=2)
        
        # Save detailed format (full cookie info)
        with open("cookies_detailed.json", "w") as f:
            json.dump(detailed_cookies, f, indent=2)
        
        print(f"✓ Extracted {len(simple_cookies)} Google cookies")
        print(f"✓ Saved to cookies.json (simple format)")
        print(f"✓ Saved to cookies_detailed.json (detailed format)")
        print("\nUsage with downloader:")
        print("  python google_takeout_downloader.py urls.txt --cookies cookies.json")
        
    except Exception as e:
        print(f"Error extracting cookies: {e}")
        print("\nTroubleshooting:")
        print("1. Close Chromium/Chrome completely")
        print("2. Make sure you're logged into Google")
        print("3. Try running with sudo if permission denied")
        sys.exit(1)

if __name__ == "__main__":
    main()