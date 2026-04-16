from _imports import Blueprint, jsonify


websocket_bp = Blueprint('websocket', __name__)


@websocket_bp.route('/ws/status', methods=['GET'])
def ws_status():
    return jsonify({"status": "connected", "service": "efficiency-websocket"})


@websocket_bp.route('/ws/subscribe', methods=['POST'])
def ws_subscribe():
    return jsonify({"status": "subscribed"})


@websocket_bp.route('/ws/unsubscribe', methods=['POST'])
def ws_unsubscribe():
    return jsonify({"status": "unsubscribed"})