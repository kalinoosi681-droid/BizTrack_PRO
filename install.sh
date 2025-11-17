#!/bin/bash
echo "Installing BizTrack PRO dependencies..."
pip install -r requirements.txt --quiet
echo "Done!"
echo ""
echo "Run the app:"
echo "   python biztrack.py          # CLI mode"
echo "   python biztrack.py --web    # Web dashboard at http://127.0.0.1:5000"
echo "   python biztrack.py --gui    # Tkinter GUI"
