import os
import sys

# Since this file is now in the 'web' directory, and we run it as a script,
# the 'web' directory is automatically added to sys.path.
# We can import app directly.

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
    
    # threads=16: Number of threads to process requests
    # Increased for better concurrency
    serve(app, host='0.0.0.0', port=8080, threads=16)
