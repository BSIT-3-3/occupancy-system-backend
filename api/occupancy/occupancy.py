from flask import Blueprint, Flask, jsonify

app = Flask(__name__)

rooms_bp = Blueprint("rooms", __name__, url_prefix="/api/rooms")

@rooms_bp.get("/<int:room_id>/occupancy")
def get_current_occupancy(room_id: int):
    """Retrieve the latest available occupancy status for one room."""
    if _find_room(room_id) is None:
        return _error("Room not found", 404)

    occupancy = rooms.get(room_id)
    if occupancy is None:
        return _error("Occupancy data is not available for this room", 404)

    return jsonify(occupancy)

app.register_blueprint(rooms_bp)

@app.get("/")
def root():
    """Confirm that the API is running."""
    return jsonify({"message": "Room Occupancy API is running"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
