#!/usr/bin/env python3
"""
Google Takeout Downloader
Downloads Google Takeout archives with resume capability and concurrent downloads.
"""

import os
import sys
import json
import time
import argparse
import requests
import threading
from pathlib import Path
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class DownloadStatus:
    url: str
    filename: str
    status: str  # pending, downloading, completed, failed, expired
    bytes_downloaded: int = 0
    total_bytes: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0

class TakeoutDownloader:
    def __init__(self, output_dir: str, max_workers: int = 4, chunk_size: int = 8192, cookies_file: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.progress_file = self.output_dir / "download_progress.json"
        self.downloads: Dict[str, DownloadStatus] = {}
        self.lock = threading.Lock()
        self.cookies = {}
        
        # Load cookies if provided
        if cookies_file:
            self.load_cookies(cookies_file)
        
        # Load existing progress
        self.load_progress()

    def load_cookies(self, cookies_file: str):
        """Load cookies from file (JSON or Netscape format)"""
        try:
            with open(cookies_file, 'r') as f:
                content = f.read()
                
                # Try JSON format first
                if content.strip().startswith('[') or content.strip().startswith('{'):
                    cookies_data = json.loads(content)
                    if isinstance(cookies_data, list):
                        # Cookie-Editor format
                        for cookie in cookies_data:
                            if 'name' in cookie and 'value' in cookie:
                                self.cookies[cookie['name']] = cookie['value']
                    elif isinstance(cookies_data, dict):
                        # Simple key-value format
                        self.cookies = cookies_data
                else:
                    # Netscape cookie format (from curl)
                    for line in content.split('\n'):
                        if line and not line.startswith('#'):
                            parts = line.strip().split('\t')
                            if len(parts) >= 7:
                                self.cookies[parts[5]] = parts[6]
                
                print(f"Loaded {len(self.cookies)} cookies from {cookies_file}")
        except Exception as e:
            print(f"Warning: Could not load cookies from {cookies_file}: {e}")

    def load_progress(self):
        """Load download progress from JSON file"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    for url, status_dict in data.items():
                        self.downloads[url] = DownloadStatus(**status_dict)
                print(f"Loaded progress for {len(self.downloads)} downloads")
            except Exception as e:
                print(f"Warning: Could not load progress file: {e}")

    def save_progress(self):
        """Save download progress to JSON file"""
        with self.lock:
            try:
                data = {url: asdict(status) for url, status in self.downloads.items()}
                with open(self.progress_file, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"Warning: Could not save progress: {e}")

    def extract_filename_from_url(self, url: str) -> str:
        """Extract filename from Google Takeout URL"""
        parsed = urlparse(url)
        
        # Try to get filename from URL path
        if parsed.path:
            filename = Path(parsed.path).name
            if filename and filename.endswith('.zip'):
                return unquote(filename)
        
        # Fallback: extract from takeout pattern
        if 'takeout-' in url:
            start = url.find('takeout-')
            end = url.find('.zip', start)
            if end != -1:
                return url[start:end+4]
        
        # Final fallback: generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"takeout_download_{timestamp}.zip"

    def get_file_size_from_headers(self, url: str) -> Optional[int]:
        """Get file size from HTTP headers without downloading"""
        try:
            response = requests.head(url, timeout=30, allow_redirects=True)
            if response.status_code == 200:
                content_length = response.headers.get('content-length')
                if content_length:
                    return int(content_length)
        except Exception as e:
            print(f"Could not get file size for {url}: {e}")
        return None

    def download_file(self, url: str) -> bool:
        """Download a single file with resume capability"""
        # Update status
        if url not in self.downloads:
            filename = self.extract_filename_from_url(url)
            self.downloads[url] = DownloadStatus(
                url=url,
                filename=filename,
                status="pending"
            )
        
        download_status = self.downloads[url]
        file_path = self.output_dir / download_status.filename
        
        # Check if already completed
        if download_status.status == "completed" and file_path.exists():
            print(f"✓ Already completed: {download_status.filename}")
            return True
        
        # Update status to downloading
        download_status.status = "downloading"
        download_status.started_at = datetime.now().isoformat()
        self.save_progress()
        
        try:
            # Check existing file size for resume
            resume_pos = 0
            if file_path.exists():
                resume_pos = file_path.stat().st_size
                print(f"Resuming {download_status.filename} from byte {resume_pos}")
            
            # Setup headers for resume
            headers = {}
            if resume_pos > 0:
                headers['Range'] = f'bytes={resume_pos}-'
            
            # Setup cookies if available
            cookies_dict = None
            if self.cookies:
                cookies_dict = self.cookies
            
            # Start download
            response = requests.get(url, headers=headers, cookies=cookies_dict, stream=True, timeout=30)
            
            # Check for expired link
            if response.status_code == 403 or response.status_code == 404:
                download_status.status = "expired"
                download_status.error_message = f"Link expired (HTTP {response.status_code})"
                self.save_progress()
                print(f"✗ Link expired: {download_status.filename}")
                return False
            
            # Check for partial content or success
            if response.status_code not in [200, 206]:
                raise requests.exceptions.RequestException(f"HTTP {response.status_code}")
            
            # Get total file size
            if download_status.total_bytes == 0:
                if response.status_code == 206:
                    # Partial content - extract from Content-Range header
                    content_range = response.headers.get('content-range', '')
                    if content_range:
                        total = content_range.split('/')[-1]
                        if total.isdigit():
                            download_status.total_bytes = int(total)
                else:
                    # Full download
                    content_length = response.headers.get('content-length')
                    if content_length:
                        download_status.total_bytes = int(content_length)
            
            # Open file for writing (append mode for resume)
            mode = 'ab' if resume_pos > 0 else 'wb'
            with open(file_path, mode) as f:
                downloaded = resume_pos
                download_status.bytes_downloaded = downloaded
                
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        download_status.bytes_downloaded = downloaded
                        
                        # Update progress periodically
                        if downloaded % (self.chunk_size * 100) == 0:
                            self.save_progress()
            
            # Mark as completed
            download_status.status = "completed"
            download_status.completed_at = datetime.now().isoformat()
            self.save_progress()
            print(f"✓ Completed: {download_status.filename} ({downloaded:,} bytes)")
            return True
            
        except Exception as e:
            download_status.status = "failed"
            download_status.error_message = str(e)
            download_status.retry_count += 1
            self.save_progress()
            print(f"✗ Failed: {download_status.filename} - {e}")
            return False

    def load_urls_from_file(self, urls_file: str) -> List[str]:
        """Load URLs from text file"""
        urls = []
        try:
            with open(urls_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and line.startswith('http'):
                        urls.append(line)
            print(f"Loaded {len(urls)} URLs from {urls_file}")
            return urls
        except Exception as e:
            print(f"Error loading URLs from {urls_file}: {e}")
            return []

    def get_pending_urls(self, all_urls: List[str]) -> List[str]:
        """Get URLs that need to be downloaded"""
        pending = []
        for url in all_urls:
            if url not in self.downloads:
                pending.append(url)
            elif self.downloads[url].status in ["pending", "failed"]:
                # Retry failed downloads (with limit)
                if self.downloads[url].retry_count < 3:
                    pending.append(url)
        return pending

    def print_summary(self):
        """Print download summary"""
        completed = sum(1 for d in self.downloads.values() if d.status == "completed")
        failed = sum(1 for d in self.downloads.values() if d.status == "failed")
        expired = sum(1 for d in self.downloads.values() if d.status == "expired")
        total = len(self.downloads)
        
        print(f"\n=== Download Summary ===")
        print(f"Total files: {total}")
        print(f"Completed: {completed}")
        print(f"Failed: {failed}")
        print(f"Expired: {expired}")
        
        if failed > 0:
            print(f"\nFailed downloads:")
            for download in self.downloads.values():
                if download.status == "failed":
                    print(f"  - {download.filename}: {download.error_message}")
        
        if expired > 0:
            print(f"\nExpired links:")
            for download in self.downloads.values():
                if download.status == "expired":
                    print(f"  - {download.filename}")

    def download_all(self, urls_file: str):
        """Download all files from URLs file"""
        urls = self.load_urls_from_file(urls_file)
        if not urls:
            print("No valid URLs found in file")
            return
        
        # Initialize download status for all URLs
        for url in urls:
            if url not in self.downloads:
                filename = self.extract_filename_from_url(url)
                self.downloads[url] = DownloadStatus(
                    url=url,
                    filename=filename,
                    status="pending"
                )
        
        pending_urls = self.get_pending_urls(urls)
        if not pending_urls:
            print("All downloads already completed!")
            self.print_summary()
            return
        
        print(f"Starting download of {len(pending_urls)} files with {self.max_workers} concurrent workers")
        
        # Download with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all pending downloads
            future_to_url = {executor.submit(self.download_file, url): url for url in pending_urls}
            
            # Process completed downloads
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    success = future.result()
                    filename = self.downloads[url].filename
                    if success:
                        print(f"✓ Successfully downloaded: {filename}")
                    else:
                        print(f"✗ Failed to download: {filename}")
                except Exception as e:
                    print(f"✗ Exception downloading {url}: {e}")
        
        self.print_summary()

def main():
    parser = argparse.ArgumentParser(description="Download Google Takeout archives with resume capability")
    parser.add_argument("urls_file", help="Text file containing download URLs (one per line)")
    parser.add_argument("--output-dir", "-o", default="./downloads", help="Directory to save downloads (default: ./downloads)")
    parser.add_argument("--max-workers", "-w", type=int, default=4, help="Maximum concurrent downloads (default: 4)")
    parser.add_argument("--chunk-size", "-c", type=int, default=8192, help="Download chunk size in bytes (default: 8192)")
    parser.add_argument("--cookies", help="Path to cookies file (JSON or Netscape format)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.urls_file):
        print(f"Error: URLs file '{args.urls_file}' not found")
        sys.exit(1)
    
    downloader = TakeoutDownloader(
        output_dir=args.output_dir,
        max_workers=args.max_workers,
        chunk_size=args.chunk_size,
        cookies_file=args.cookies
    
    try:
        downloader.download_all(args.urls_file)
    except KeyboardInterrupt:
        print("\nDownload interrupted by user. Progress saved.")
        downloader.save_progress()
        sys.exit(0)

if __name__ == "__main__":
    main()