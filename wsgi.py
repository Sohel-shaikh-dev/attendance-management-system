from app import app
import os

if __name__ == "__main__":
    # In production, Gunicorn will serve the app, so this block is bypassed.
    # It only runs when executed explicitly via `python wsgi.py`
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
