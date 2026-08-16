from flask import Flask, jsonify, request
from flask_cors import CORS

import sender

app = Flask(__name__)
# Allow the Vercel frontend to call this API cross-origin.
CORS(app)


@app.route("/")
def home():
    return jsonify(
        {
            "service": "netflix-trial-backend",
            "health": "/healthz",
            "send": "POST /api/send with JSON body {email}",
        }
    )


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/api/send", methods=["POST"])
def api_send():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    # Cookie from the frontend "cookie editor" — can be a bare nfvdid value,
    # a Cookie header line, or the JSON array exported by a cookie editor.
    cookie_input = data.get("cookie") or data.get("nfvdid") or data.get("cookieJson")
    ok, message = sender.send_trial(email, cookie_input)
    return jsonify({"ok": ok, "message": message})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
