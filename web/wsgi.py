import os
import sys
import eventlet

# Patch for better performance (Web Server only)
eventlet.monkey_patch()

# Since this file is now in the 'web' directory, and we run it as a script,
# the 'web' directory is automatically added to sys.path.
# We can import app directly.

from __init__ import create_app

app = create_app()

if __name__ == "__main__":
    from waitress import serve
    print("=======================================================")
    print("   Auto Grading System - Production Server (Windows)")
    print("=======================================================")
    print(" * Serving on http://0.0.0.0:8080")
    print(" * Mode: Production (Waitress)")
    print(" * Press Ctrl+C to stop")
    print("=======================================================")
    
    # threads: Dynamic adjustment based on CPU
    # For personal laptops, we balance concurrency with system responsiveness.
    # IO-bound web threads can be higher than CPU cores, but we cap it to reasonable limits.
    try:
        import os
        # Usually 2x logical cores is a good sweet spot for Waitress on Windows
        thread_count = min(max(os.cpu_count() * 2, 8), 24)
        print(f" * Threads Settings: {thread_count} worker threads allowed")
    except:
        thread_count = 16

    serve(app, host='0.0.0.0', port=8080, threads=thread_count)
