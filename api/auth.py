# =============================================================================
# api/auth.py — LOGIN, PASSWORD, AND SESSION MANAGEMENT
# =============================================================================
# Handles password hashing, login page, session checks.
# Import login_required and apply it to any route you want protected.
#
# TO ADD A NEW AUTH METHOD (e.g. API keys): add logic here, not in routes.py
# =============================================================================

import hashlib
import secrets
import os
from functools import wraps
from flask import session, redirect, request, jsonify

# Loaded from .auth file on startup — set via the Security page in the GUI
_password_hash = None


def load_saved_password():
    """Loads a previously set password from the .auth file."""
    global _password_hash
    if os.path.exists(".auth"):
        with open(".auth") as f:
            _password_hash = f.read().strip()


def hash_password(password: str) -> str:
    """Returns a SHA-256 hash of the password."""
    return hashlib.sha256(password.encode()).hexdigest()


def set_password(new_password: str) -> bool:
    """
    Sets a new password. Saves hash to .auth file.
    Returns False if password is too short.
    """
    global _password_hash
    if len(new_password) < 6:
        return False
    _password_hash = hash_password(new_password)
    with open(".auth", "w") as f:
        f.write(_password_hash)
    return True


def check_password(password: str) -> bool:
    """Returns True if the password matches, or if no password is set."""
    if not _password_hash:
        return True  # No password set — allow through
    return hash_password(password) == _password_hash


def is_password_set() -> bool:
    """Returns True if a password has been configured."""
    return bool(_password_hash)


def login_required(f):
    """
    Decorator to protect routes. Redirects to /login if not authenticated.
    API routes get a 401 JSON response instead of a redirect.
    Usage: @login_required above any route function.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _password_hash:
            return f(*args, **kwargs)  # No password set — open access
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


def get_login_page(error: bool = False) -> str:
    """Returns the HTML for the login page."""
    error_html = '<p style="color:#bf616a;font-size:12px;margin-bottom:12px;font-family:monospace">Incorrect password</p>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>PredBot — Sign In</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
  <style>
    * {{ box-sizing:border-box; margin:0; padding:0 }}
    body {{ font-family:Inter,sans-serif; background:#eceff4; display:flex; align-items:center; justify-content:center; min-height:100vh }}
    .box {{ background:#fff; border:1px solid #d8dee9; border-radius:12px; padding:40px; width:340px; box-shadow:0 4px 20px rgba(46,52,64,.08) }}
    .logo {{ font-size:22px; font-weight:600; color:#2e3440; margin-bottom:4px }}
    .logo span {{ color:#5e81ac }}
    .sub {{ font-size:13px; color:#7b8898; margin-bottom:28px }}
    label {{ font-size:11px; font-weight:500; color:#4c566a; display:block; margin-bottom:6px; letter-spacing:.03em }}
    input {{ width:100%; padding:9px 12px; border:1px solid #d8dee9; border-radius:7px; font-size:14px; outline:none; margin-bottom:16px; font-family:Inter,sans-serif; background:#eceff4; color:#2e3440 }}
    input:focus {{ border-color:#5e81ac; background:#fff }}
    button {{ width:100%; padding:10px; background:#5e81ac; color:#fff; border:none; border-radius:7px; font-size:14px; font-weight:500; cursor:pointer; font-family:Inter,sans-serif }}
    button:hover {{ background:#4e6e96 }}
  </style>
</head>
<body>
  <div class="box">
    <div class="logo">Pred<span>Bot</span></div>
    <div class="sub">Sign in to continue</div>
    {error_html}
    <form method="post">
      <label>Password</label>
      <input type="password" name="password" autofocus placeholder="Enter your password"/>
      <button type="submit">Sign in</button>
    </form>
  </div>
</body>
</html>"""