# Substack Scraper

A one-click-ish Substack inbox article extractor.  
Works on WSL, just install requirements and go.

## Setup

Install WSL
open windows CMD in admin and run
```bash
wsl --install
```

Search UBUNTU in search bar and run these on command line
```bash
sudo apt update
sudo apt install python3 python3-pip -y
git clone https://github.com/Harrenn/substack-inbox-scraper.git
cd substack-inbox-scraper
pip install -r requirements.txt
python3 -m playwright install
python3 play.py
```
