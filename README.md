# Substack Scraper

A one-click-ish Substack inbox article extractor.  
Works on WSL, just install requirements and go.

## Setup

Install WSL
open windows CMD in admin and run
```bash
wsl --install
```

Search UBUNTU in search bar and run these on command line (Only Once)
```bash
sudo apt update
sudo apt install python3 python3-pip -y
git clone https://github.com/Harrenn/substack-inbox-scraper.git
cd substack-inbox-scraper
pip install -r requirements.txt
python3 -m playwright install
python3 play.py
```

After installation you only need to run (make sure you are on the right directory by running "cd substack-inbox-scraper")
```bash
python3 play.py
```

