from __init__ import create_app, socketio
import sys

# Create the application instance
app = create_app()

if __name__ == '__main__':
    # Disable debug mode in production/packaged environment
    debug_mode = not getattr(sys, 'frozen', False)
    # Use socketio.run for WebSocket capability
    socketio.run(app, debug=debug_mode, port=5000)