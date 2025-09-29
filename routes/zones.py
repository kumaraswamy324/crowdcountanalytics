#zones.py
from flask import Blueprint, request, jsonify
import os
import json

zones_bp = Blueprint("zones", __name__, url_prefix="/zones")

ZONES_FILE = "zones.json"

# Load zones from persistent file
def load_zones_from_file():
    if os.path.exists(ZONES_FILE):
        try:
            with open(ZONES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

# Save zones to persistent file
def save_zones_to_file(zones):
    try:
        with open(ZONES_FILE, "w") as f:
            json.dump(zones, f, indent=2)
    except Exception as e:
        print("Error saving zones:", e)

# Initialize zones storage
zones_storage = load_zones_from_file()

@zones_bp.route("/save", methods=["POST"])
def save_zone():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No JSON provided"}), 400

    try:
        name = data.get("name", f"Zone {len(zones_storage) + 1}")
        x1, y1 = int(data["x1"]), int(data["y1"])
        x2, y2 = int(data["x2"]), int(data["y2"])
    except Exception:
        return jsonify({"status": "error", "message": "Invalid coordinates"}), 400

    x1, x2 = min(x1, x2), max(x1, x2)
    y1, y2 = min(y1, y2), max(y1, y2)

    zones_storage.append({"name": name, "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    save_zones_to_file(zones_storage)
    return jsonify({"status": "success", "zones": zones_storage})

@zones_bp.route("/list", methods=["GET"])
def list_zones():
    return jsonify({"status": "success", "zones": zones_storage})

@zones_bp.route("/delete/<int:index>", methods=["DELETE"])
def delete_zone(index):
    if 0 <= index < len(zones_storage):
        zones_storage.pop(index)
        save_zones_to_file(zones_storage)
        return jsonify({"status": "success", "zones": zones_storage})
    return jsonify({"status": "error", "message": "Invalid zone index"}), 400

@zones_bp.route("/clear", methods=["POST"])
def clear_zones():
    zones_storage.clear()
    save_zones_to_file(zones_storage)
    return jsonify({"status": "success", "zones": zones_storage})
