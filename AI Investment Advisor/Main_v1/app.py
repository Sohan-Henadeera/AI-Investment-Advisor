# =============================================================================
# TO RUN:  python app.py
# THEN:    open http://localhost:5000 in your browser
# =============================================================================

import secrets
import os
from flask import Flask, send_file

from config       import PORT, HOST
from database     import setup_database
from api.routes   import bp as routes_blueprint
from api.auth     import load_saved_password

# Create the Flask app
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Register all routes from api/routes.py 
app.register_blueprint(routes_blueprint)

# Serve the GUI
@app.route("/")
def index():
    """Serves the main GUI file."""
    gui_path = os.path.join(os.path.dirname(__file__), "gui.html")
    if os.path.exists(gui_path):
        return open(gui_path, encoding="utf-8").read()
    return "<h1>gui.html not found — make sure it's in the same folder as app.py</h1>"


# Startup
if __name__ == "__main__":
    setup_database()

    load_saved_password()

    print("\n" + "="*52)
    print("  PredBot v1 — Starting")
    print("="*52)
    print(f"  Open:    http://localhost:{PORT}")
    print(f"  Mode:    Paper trading (no real money)")
    print(f"  AI:      Local Ollama (zero cost)")
    print(f"  Data:    {os.path.abspath('predbot.db')}")
    print("="*52 + "\n")

    app.run(
        host=HOST,
        port=PORT,
        debug=False,      
        use_reloader=False 
    )