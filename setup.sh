#!/bin/bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install
echo "✅ Setup complete. Run the script with: source venv/bin/activate && python run_scraper.py"
