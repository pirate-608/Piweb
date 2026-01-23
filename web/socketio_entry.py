
# ---- gevent patch_all 必须最早 ----
import gevent.monkey
gevent.monkey.patch_all(ssl=True, aggressive=True)

from web.__init__ import create_app, socketio

app = create_app()

if __name__ == "__main__":
    print("Starting socketio server on 0.0.0.0:8080")
    socketio.run(app, host="0.0.0.0", port=8080)
