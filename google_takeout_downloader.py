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
import zipfile
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
    def __init__(self, output_dir: str, max_workers: int = 4, chunk_size: int = 8192, headers_file: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.progress_file = self.output_dir / "download_progress.json"
        self.downloads: Dict[str, DownloadStatus] = {}
        self.lock = threading.Lock()
        self.cookies = {}
        self.custom_headers = {}
        
        # Load headers and cookies
        if headers_file:
            self.load_headers(headers_file)
        elif Path("headers.json").exists():
            self.load_headers("headers.json")
        
        # Load existing progress
        self.load_progress()

    def load_headers(self, headers_file: str):
        """Load headers and cookies from JSON file"""
        try:
            with open(headers_file, 'r') as f:
                data = json.load(f)
                
                # Load cookies
                if 'cookies' in data:
                    self.cookies = data['cookies']
                    print(f"Loaded {len(self.cookies)} cookies from {headers_file}")
                
                # Load custom headers
                if 'headers' in data:
                    self.custom_headers = data['headers']
                    print(f"Loaded {len(self.custom_headers)} custom headers from {headers_file}")
                
                # Backward compatibility - if file is old format (just cookies)
                if 'cookies' not in data and 'headers' not in data:
                    self.cookies = data
                    print(f"Loaded {len(self.cookies)} cookies from {headers_file} (legacy format)")
                
        except Exception as e:
            print(f"Warning: Could not load headers from {headers_file}: {e}")

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

    def validate_zip_file(self, file_path: Path) -> bool:
        """Validate that downloaded file is a proper ZIP archive, not HTML"""
        try:
            # Check if file is too small (HTML pages are usually < 50KB)
            if file_path.stat().st_size < 50000:  # 50KB threshold
                return False
            
            # Try to open as ZIP file
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Test if we can read the file list
                zip_file.namelist()
                return True
        except (zipfile.BadZipFile, OSError):
            return False
    
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
        
        # Check if already completed and validate file
        if download_status.status == "completed" and file_path.exists():
            if self.validate_zip_file(file_path):
                print(f"✓ Already completed: {download_status.filename}")
                return True
            else:
                print(f"⚠ Invalid ZIP file detected: {download_status.filename} (likely HTML, re-downloading)")
                download_status.status = "pending"  # Reset to re-download
        
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
            
            # Setup headers from headers.json
            headers = self.custom_headers.copy() if self.custom_headers else {}
            
            # Add range header for resume (must be last)
            if resume_pos > 0:
                headers['Range'] = f'bytes={resume_pos}-'
            
            # Setup cookies if available
            cookies_dict = None
            if self.cookies:
                cookies_dict = self.cookies
            
            # Start download
            response = requests.get(url, headers=headers, cookies=cookies_dict, stream=True, timeout=30, allow_redirects=True)
            
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
            
            # Final progress update with actual file size
            download_status.bytes_downloaded = downloaded
            download_status.total_bytes = downloaded
            self.save_progress()
            
            # Validate downloaded file
            if not self.validate_zip_file(file_path):
                download_status.status = "failed"
                download_status.error_message = "Downloaded file is not a valid ZIP archive (likely HTML login page)"
                self.save_progress()
                print(f"✗ Invalid file: {download_status.filename} - not a valid ZIP archive")
                return False
            
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
            elif self.downloads[url].status in ["completed", "downloading"]:
                # Check if file exists and validate it
                file_path = self.output_dir / self.downloads[url].filename
                if file_path.exists():
                    if self.validate_zip_file(file_path):
                        # File is valid - update status and progress to match actual file
                        actual_size = file_path.stat().st_size
                        self.downloads[url].status = "completed"
                        self.downloads[url].bytes_downloaded = actual_size
                        self.downloads[url].total_bytes = actual_size
                        self.downloads[url].completed_at = datetime.now().isoformat()
                        # Don't add to pending
                    else:
                        print(f"⚠ Invalid ZIP file detected: {self.downloads[url].filename} (likely HTML, marking for re-download)")
                        self.downloads[url].status = "pending"
                        self.downloads[url].error_message = "Previous download was HTML, not ZIP"
                        pending.append(url)
                else:
                    # File missing, re-download
                    self.downloads[url].status = "pending"
                    pending.append(url)
        
        # Save any progress updates made during validation
        self.save_progress()
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
    parser.add_argument("--headers", help="Path to headers file (JSON format with cookies and headers)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.urls_file):
        print(f"Error: URLs file '{args.urls_file}' not found")
        sys.exit(1)
    
    downloader = TakeoutDownloader(
        output_dir=args.output_dir,
        max_workers=args.max_workers,
        chunk_size=args.chunk_size,
        headers_file=args.headers
    )
    
    try:
        downloader.download_all(args.urls_file)
    except KeyboardInterrupt:
        print("\nDownload interrupted by user. Progress saved.")
        downloader.save_progress()
        sys.exit(0)

if __name__ == "__main__":
    main()