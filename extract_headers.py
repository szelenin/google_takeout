#!/usr/bin/env python3
"""
Extract headers and cookies from Chromium/Chrome for Google Takeout downloads
Supports automatic extraction from browser and cURL command parsing
Works on Raspberry Pi and other Linux systems
"""

import sqlite3
import json
import os
import sys
import shutil
import argparse
import re
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

def parse_curl_command(curl_cmd):
    """Parse cURL command to extract cookies and headers"""
    cookies = {}
    headers = {}
    
    # Extract cookies from -b parameter
    cookie_match = re.search(r"-b\s+'([^']+)'", curl_cmd)
    if cookie_match:
        cookie_string = cookie_match.group(1)
        for cookie_pair in cookie_string.split('; '):
            if '=' in cookie_pair:
                name, value = cookie_pair.split('=', 1)
                cookies[name.strip()] = value.strip()
    
    # Extract headers from -H parameters
    header_matches = re.findall(r"-H\s+'([^:]+):\s*([^']+)'", curl_cmd)
    for header_name, header_value in header_matches:
        headers[header_name.strip()] = header_value.strip()
    
    return cookies, headers

def main():
    parser = argparse.ArgumentParser(description="Extract headers and cookies for Google Takeout downloads")
    parser.add_argument("--curl", help="cURL command to parse for headers and cookies")
    parser.add_argument("--curl-file", help="File containing cURL command")
    
    args = parser.parse_args()
    
    # Always start with browser cookies
    browser_cookies = {}
    
    # Find and extract from browser database
    cookies_db = find_chromium_cookies_db()
    
    if cookies_db:
        print(f"Found cookies database: {cookies_db}")
        try:
            browser_cookies, detailed_cookies = extract_google_cookies(cookies_db)
            print(f"✓ Extracted {len(browser_cookies)} cookies from browser")
        except Exception as e:
            print(f"Warning: Could not extract browser cookies: {e}")
    else:
        print("Warning: Could not find browser cookies database")
    
    # Parse cURL command if provided
    curl_cookies = {}
    curl_headers = {}
    
    curl_command = None
    if args.curl:
        curl_command = args.curl
    elif args.curl_file:
        try:
            with open(args.curl_file, 'r') as f:
                curl_command = f.read().strip()
        except Exception as e:
            print(f"Error reading cURL file {args.curl_file}: {e}")
            sys.exit(1)
    
    if curl_command:
        print("Parsing cURL command...")
        curl_cookies, curl_headers = parse_curl_command(curl_command)
        print(f"✓ Extracted {len(curl_cookies)} cookies and {len(curl_headers)} headers from cURL")
    
    # Merge cookies (cURL takes precedence)
    final_cookies = browser_cookies.copy()
    final_cookies.update(curl_cookies)  # cURL overrides browser
    
    if not final_cookies:
        print("Error: No cookies found from browser or cURL command")
        print("Make sure you're logged into Google or provide a valid cURL command")
        sys.exit(1)
    
    # Create final headers structure
    result = {
        "cookies": final_cookies,
        "headers": curl_headers
    }
    
    # Save to headers.json
    with open("headers.json", "w") as f:
        json.dump(result, f, indent=2)
    
    # Also save detailed cookies for debugging
    if 'detailed_cookies' in locals():
        with open("cookies_detailed.json", "w") as f:
            json.dump(detailed_cookies, f, indent=2)
    
    print(f"\n✓ Final result: {len(final_cookies)} cookies, {len(curl_headers)} headers")
    print(f"✓ Saved to headers.json")
    print("\nUsage with downloader:")
    print("  python google_takeout_downloader.py urls.txt")
    
    if not curl_command:
        print("\nFor better compatibility, run with cURL command:")
        print("  python extract_headers.py --curl \"curl 'https://...' -H '...' -b '...'\"")

if __name__ == "__main__":
    main()