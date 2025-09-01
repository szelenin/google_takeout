#!/bin/bash

# Setup script for Google Takeout Downloader on Raspberry Pi

echo "Setting up Google Takeout Downloader on Raspberry Pi..."

# Update system packages
echo "Updating system packages..."
sudo apt-get update

# Install Python3 and pip if not already installed
echo "Installing Python3 and pip..."
sudo apt-get install -y python3 python3-pip

# Install virtual environment (optional but recommended)
echo "Installing python3-venv..."
sudo apt-get install -y python3-venv

# Create virtual environment (optional)
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install required Python packages
echo "Installing required Python packages..."
pip3 install -r requirements.txt

# Make the script executable
chmod +x google_takeout_downloader.py

echo "Setup complete!"
echo ""
echo "To use the downloader:"
echo "1. Add your Google Takeout URLs to urls.txt"
echo "2. Run: python3 google_takeout_downloader.py urls.txt"
echo ""
echo "Or if using virtual environment:"
echo "1. Activate: source venv/bin/activate"
echo "2. Run: python google_takeout_downloader.py urls.txt"