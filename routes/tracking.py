from flask import Blueprint, jsonify, request
from ultralytics import YOLO
import cv2
import os
import json
import time
import threading
import collections
import numpy as np  # For warmup frame


try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
    DEEPSORT_AVAILABLE = True
except ImportError:
    DEEPSORT_AVAILABLE = False
    print("Warning: DeepSort not available. Please install: pip install deep-sort-realtime")


tracking_bp = Blueprint("tracking", __name__, url_prefix="/tracking")


# YOLOv8 model
model = YOLO("yolov8n.pt")


# Warmup function to reduce first-frame lag
def warmup_model():
    dummy_frame = 255 * np.ones((640, 480, 3), dtype=np.uint8)
    for _ in range(3):
        model(dummy_frame, conf=0.5, verbose=False)


warmup_model()


# DeepSORT tracker
if DEEPSORT_AVAILABLE:
    tracker = DeepSort(
        max_age=15,
        n_init=1,
        nms_max_overlap=1.0,
        max_cosine_distance=0.15,
        nn_budget=None,
        embedder="mobilenet",
        half=True,
        bgr=True,
        embedder_gpu=True,
        polygon=False
    )
else:
    tracker = None


# Zones
ZONES_FILE = "zones.json"


# Video capture
video_path = None  # No default video
cap = None
camera_cap = None
use_camera = False
cap_lock = threading.Lock()


# Tracking state
current_tracks = []
frame_count = 0
last_update_time = time.time()
last_frame_time = 0
MIN_FRAME_INTERVAL = 0.07  # Increased for steady backend processing


# Zone counts
last_zone_counts = {}
zone_counts_history = collections.deque(maxlen=300)  # last 300 history points


# ---------------------- Utility Functions ---------------------- #


def load_zones_from_file():
    if os.path.exists(ZONES_FILE):
        try:
            with open(ZONES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def yolo_to_deepsort_format(results):
    detections = []
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(float, box.xyxy[0])
            confidence = float(box.conf[0])
            class_id = int(box.cls[0])
            class_name = model.names[class_id]
            if class_name == "person" and confidence >= 0.3:
                width = x2 - x1
                height = y2 - y1
                detections.append(([x1, y1, width, height], confidence, class_id))
    return detections


def is_person_in_zone(bbox, zone):
    x1, y1, x2, y2 = bbox
    zx1, zy1, zx2, zy2 = zone["x1"], zone["y1"], zone["x2"], zone["y2"]
    ix1, iy1 = max(x1, zx1), max(y1, zy1)
    ix2, iy2 = min(x2, zx2), min(y2, zy2)
    if ix1 >= ix2 or iy1 >= iy2:
        return False
    intersection_area = (ix2 - ix1) * (iy2 - iy1)
    bbox_area = (x2 - x1) * (y2 - y1)
    return bbox_area > 0 and (intersection_area / bbox_area) >= 0.3


def update_single_tracking_frame():
    global cap, camera_cap, use_camera, current_tracks, frame_count, last_update_time, last_zone_counts

    with cap_lock:
        # Stop if no video and camera not active
        if not use_camera and (cap is None or not cap.isOpened()):
            return None

        if use_camera:
            if camera_cap is None or not camera_cap.isOpened():
                return None
            ret, frame = camera_cap.read()
            if not ret:
                return None
        else:
            ret, frame = cap.read()
            if not ret:
                cap.release()
                cap = cv2.VideoCapture(video_path)
                ret, frame = cap.read()
                if not ret:
                    return None

    frame_count += 1

    # Resize frame for YOLO
    input_width, input_height = 640, 480
    frame_resized = cv2.resize(frame, (input_width, input_height))

    results = model(frame_resized, conf=0.5, verbose=False)
    detections = yolo_to_deepsort_format(results)

    tracks = tracker.update_tracks(detections, frame=frame_resized) if tracker else []

    formatted_tracks = []
    for track in tracks:
        if not track.is_confirmed():
            continue
        track_id = track.track_id
        ltrb = track.to_ltrb()
        det_class = track.get_det_class()
        class_name = model.names[det_class] if det_class is not None else "person"
        det_conf = track.get_det_conf()
        confidence = float(det_conf) if det_conf is not None else None

        formatted_tracks.append({
            "track_id": track_id,
            "bbox": [int(x) for x in ltrb],
            "class_name": class_name,
            "confidence": confidence
        })

    current_tracks = formatted_tracks
    last_update_time = time.time()

    # Calculate zone counts
    zones = load_zones_from_file()
    zone_counts = {zone["name"]: 0 for zone in zones}
    for track in current_tracks:
        bbox = track["bbox"]
        for zone in zones:
            if is_person_in_zone(bbox, zone):
                zone_counts[zone["name"]] += 1

    last_zone_counts = zone_counts

    # Append to history
    zone_counts_history.append({
        "timestamp": time.time(),
        "zone_counts": zone_counts.copy()
    })

    return formatted_tracks, zone_counts, input_width, input_height


# ---------------------- Routes ---------------------- #


@tracking_bp.route("/update", methods=["POST"])
def update_tracking():
    global last_frame_time

    now = time.time()
    if now - last_frame_time < MIN_FRAME_INTERVAL:
        return jsonify({"status": "waiting", "message": "Throttling requests"}), 429
    last_frame_time = now

    if not DEEPSORT_AVAILABLE:
        return jsonify({"status": "error", "message": "DeepSORT not available"}), 500

    try:
        result = update_single_tracking_frame()
        if result is None:
            return jsonify({"status": "error", "message": "No video or camera active"}), 400
        formatted_tracks, zone_counts, frame_width, frame_height = result
        return jsonify({
            "status": "success",
            "tracks": formatted_tracks,
            "zone_counts": zone_counts,
            "frame_count": frame_count,
            "timestamp": last_update_time,
            "frame_width": frame_width,
            "frame_height": frame_height,
        })
    except Exception as e:
        print(f"Error in update_tracking: {e}")
        return jsonify({"status": "error", "message": f"Tracking update failed: {e}"}), 500


@tracking_bp.route("/zone_counts", methods=["GET"])
def get_zone_counts():
    global last_zone_counts
    try:
        return jsonify({"status": "success", "zone_counts": last_zone_counts})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@tracking_bp.route("/zone_counts_history", methods=["GET"])
def get_zone_counts_history():
    try:
        limit = int(request.args.get("limit", 100))
        hist = list(zone_counts_history)[-limit:]
        return jsonify({"status": "success", "history": hist})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@tracking_bp.route("/set_video_path", methods=["POST"])
def set_video_path():
    global video_path, cap, use_camera, last_zone_counts, zone_counts_history
    try:
        data = request.get_json()
        new_path = data.get("video_path")
        if not new_path:
            return jsonify({"status": "error", "message": "No video_path provided"}), 400

        use_camera = False

        abs_path = os.path.join(os.getcwd(), new_path.lstrip('/'))
        if not os.path.exists(abs_path):
            return jsonify({"status": "error", "message": "File not found"}), 400

        # Reset zone counts and history
        last_zone_counts = {}
        zone_counts_history.clear()

        with cap_lock:
            if cap and cap.isOpened():
                cap.release()
            cap = cv2.VideoCapture(abs_path)
            video_path = abs_path
            if not cap.isOpened():
                return jsonify({"status": "error", "message": "Failed to open video at path"}), 500

        return jsonify({"status": "success", "message": f"Video source updated to {video_path}"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Exception: {str(e)}"}), 500


@tracking_bp.route("/set_camera_mode", methods=["POST"])
def set_camera_mode():
    global use_camera, cap, camera_cap
    try:
        data = request.get_json()
        enable_camera = data.get("enable_camera", False)
        with cap_lock:
            if enable_camera:
                if cap and cap.isOpened():
                    cap.release()
                if camera_cap and camera_cap.isOpened():
                    camera_cap.release()
                camera_cap = cv2.VideoCapture(0)
                if not camera_cap.isOpened():
                    camera_cap = None
                    return jsonify({"status": "error", "message": "Failed to open camera"}), 500
                use_camera = True
            else:
                if camera_cap and camera_cap.isOpened():
                    camera_cap.release()
                    camera_cap = None
                use_camera = False
        return jsonify({"status": "success", "camera_enabled": use_camera})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Exception: {str(e)}"}), 500


# ---------------------- Keepalive ---------------------- #
@tracking_bp.route("/keepalive", methods=["POST"])
def keepalive():
    return jsonify({"status": "success", "message": "Keepalive OK"})
