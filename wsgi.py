import os
import sys

# Add the 'web' directory to sys.path
# This ensures that imports inside app.py (like 'from config import Config') work correctly
web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
sys.path.insert(0, web_dir)

from app import app

if __name__ == "__main__":
    from waitress import serve
    print("=======================================================")
    print("   Auto Grading System - Production Server (Windows)")
    print("=======================================================")
    print(" * Serving on http://0.0.0.0:8080")
    print(" * Mode: Production (Waitress)")
    print(" * Press Ctrl+C to stop")
    print("=======================================================")
    
    # threads=4: Number of threads to process requests
    serve(app, host='0.0.0.0', port=8080, threads=4)
