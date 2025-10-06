# app.py
from flask import Flask, render_template, request
from routes.auth import auth_bp, token_required
from routes.zones import zones_bp
from routes.tracking import tracking_bp

import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key"

# ----------------------------
# Register blueprints
# ----------------------------
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(zones_bp, url_prefix="/zones")
app.register_blueprint(tracking_bp, url_prefix="/tracking")

# ----------------------------
# Routes
# ----------------------------
@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/zones")
@token_required
def zones(current_user):
    tab = request.args.get("tab", "draw")  # default = draw
    return render_template("zones.html", tab=tab)

@app.route("/zone_counts")
@token_required
def zone_counts(current_user):
    return render_template("zone_counts.html")

@app.route("/tracking_page")
@token_required
def tracking_page(current_user):
    """
    Page for live tracking results
    """
    return render_template("tracking.html")

# ----------------------------
# File upload route (optional)
# ----------------------------
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/upload_video", methods=["POST"])
def upload_video():
    if "video" not in request.files:
        return {"status": "error", "message": "No file uploaded"}, 400

    file = request.files["video"]
    if file.filename == "":
        return {"status": "error", "message": "No filename"}, 400

    # Save uploaded file
    filename = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    # URL to access uploaded video
    file_url = f"/static/uploads/{filename}"
    return {"status": "success", "url": file_url}

# ----------------------------
# Run the app
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True)
