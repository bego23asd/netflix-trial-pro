import argparse
import asyncio
import json
import os
import uuid

import httpx

from flask import Flask, jsonify, request
from flask_cors import CORS

URL = "https://web.prod.cloud.netflix.com/graphql"

NFVDID_VALUE = "BQFmAAEBEDfQY0dAGiJZuocAfFU2CQpAYdUwSM-D1OYmnErF2ElCBLm3CS95c_ywNg2ALWYqpR11S7Q7F8GGn_WlsEleYshSjx9uKQE-KVY35tPLE1ZtgQ%3D%3D"

RECAPTCHA_SITE_KEY = "6LdqW_EqAAAAAO87Fb_kcZfNzs0IqJRcKiJDYpUv"

# Optional cookie.txt next to this file — drop your cookie-export JSON array or
# the bare nfvdid value there and it is used VERBATIM (no transcription risk).
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookie.txt")

# Merged web API (from app.py) — the Flask app that Render serves via gunicorn.
app = Flask(__name__)
# Allow the Vercel frontend to call this API cross-origin.
CORS(app)


def _load_cookie_file():
    """Read cookie.txt (if present): raw JSON array, Cookie line, or bare value."""
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def make_payloads(email, flwssn):
    payload1 = {
        "operationName": "CLCSWebInitSignup",
        "variables": {
            "inputNode": "WELCOME",
            "locale": "en-IN",
            "inputFields": [
                {"name": "flwssn", "value": {"stringValue": flwssn}},
                {"name": "email", "value": {"stringValue": email}},
                {"name": "recaptchaError", "value": {"stringValue": "LOAD_TIMED_OUT"}},
                {"name": "recaptchaResponseTime", "value": {}},
                {"name": "recaptchaSiteKey", "value": {"stringValue": RECAPTCHA_SITE_KEY}},
                {"name": "recaptchaToken", "value": {}},
            ],
        },
        "extensions": {
            "persistedQuery": {
                "id": "5d76d6a0-ccfe-4c31-b587-b4e1954732ca",
                "version": 102,
            }
        },
    }

    payload2 = {
        "operationName": "CLCSScreenUpdate",
        "variables": {
            "format": "HTML",
            "imageFormat": "PNG",
            "locale": "en-IN",
            "serverState": (
                "Bgjru+vcAxLTAf/qOOEwXPLVxW+7Jod9WpjYuKN8j1qfhQpzCK4mmQts5eMSeaP+l"
                "7s6NKcNBO4rmYabFFCVnMpCH3ib4AicvXAKm30Z+s5W3Cst0D0BK5x/pwn3QmByi/OgGwU/fzaiR5oxSlZe4fKVexWHISkE4GMzJqLaaXQR0M"
                "73ynZB9idNBfqsz3RA5WJN+DGAbVUOZlWl8eZqffvQpp/5MGubeQFpdwKqkAx1nHh7/xI1i9tDU0KLgrvkZrbe6nQ1MX2nc9TBxqnVVxtc3ptHdqy"
                "dP1wlIu0YBiIOCgydgLg1SvK6tSPOff8="
            ),
            "serverScreenUpdate": (
                "Bgjru+vcAxKSAjDnHOxlaIbFSbwaWzZo/REHFnNG7OtpcXdKTDlcL4/o+huGi/fNW+jrqNDqDSsv1iytiG/ZtvO9ierUE9M1Kc/yEj9JsSiG"
                "3XpPciFDzPd6psSaG68XLbos+Qie0wniXCtJyWDLDuLd9ayCMB8qGCxwbov6B41kCQY/zArwlecm0GNoJdd5jvZfBJVtytD6mMCYnPA/9zhX4okj"
                "+6IGet9xOCYt76IDiuyESxgKbaOLcd6DQIDSBf4m/lYi2Tasj7olPkCaDIXxjU+0UY+b7eDyhvi2if2vt6510ARrGsSZq8DaazQmrpAbfiCW47s1/"
                "1mR59vUMYeT8VCqqAvbNwipqyP1DQMHtoTnCoWns0+x6IgYBiIOCgx9EW4i3i9SUswnHEg="
            ),
            "inputFields": [
                {"name": "email", "value": {"stringValue": email}},
                {"name": "pipcConsent", "value": {"booleanValue": False}},
            ],
        },
        "extensions": {
            "persistedQuery": {
                "id": "0fd81de7-07af-4c7d-802f-0f4ea4181aa3",
                "version": 102,
            }
        },
    }

    return payload1, payload2


def make_headers():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Origin": "https://www.netflix.com",
        "Referer": "https://www.netflix.com/",
        "Accept-Language": "en-US,en;q=0.9",
        "x-netflix.request.id": str(uuid.uuid4()),
        "x-netflix.request.toplevel.uuid": str(uuid.uuid4()),
        "x-netflix.request.clcs.bucket": "high",
        "x-netflix.context.form-factor": "phone",
        "x-netflix.context.app-version": "v38c5b0da",
        "x-netflix.context.locales": "en-in",
    }


def _split_cookie_line(cookies, line):
    """Split a 'name=value; name2=value2' cookie line into the given dict."""
    for part in line.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        cookies[name.strip()] = value.strip()


def parse_cookie_input(raw):
    """
    Accept the cookie in any export format and turn it into a dict.

    Supported inputs:
      1. JSON array from a cookie exporter / cookie editor (EditThisCookie…):
         [{"name": "nfvdid", "value": "BQF...%3D%3D"}]
      2. A plain Cookie header line:
         nfvdid=BQF...; flwssn=abc-123
      3. A bare nfvdid value:
         BQFmAAEB...

    Returns a dict like {"nfvdid": "...", "flwssn": "..."}. Anything that
    fails to parse falls back to the hardcoded NFVDID_VALUE constant.
    """
    raw = (raw or "").strip()
    if not raw:
        raw = _load_cookie_file() or ""
        raw = raw.strip()
    cookies = {}

    if not raw:
        pass
    elif raw.lower().startswith("cookie:"):
        _split_cookie_line(cookies, raw.split(":", 1)[1].strip())
    elif raw.startswith("[") or raw.startswith("{"):
        try:
            items = json.loads(raw)
            if isinstance(items, dict):
                items = [items]
            for item in items:
                if isinstance(item, dict) and item.get("name"):
                    cookies[str(item["name"])] = str(item["value"])
        except (ValueError, TypeError):
            pass
    elif "=" in raw:
        _split_cookie_line(cookies, raw)
    else:
        # Bare value — treat it as the nfvdid token itself.
        cookies["nfvdid"] = raw

    if "nfvdid" not in cookies:
        cookies["nfvdid"] = NFVDID_VALUE

    return cookies


def build_cookie_header(cookies, flwssn):
    """
    Merge the injected cookies with a fresh flwssn and output the Cookie
    header, exactly like a cookie editor would pin values into the request.
    """
    merged = dict(cookies)
    merged.setdefault("flwssn", flwssn)
    return "; ".join(f"{name}={value}" for name, value in merged.items())


def _proxy_url():
    """
    Optional egress proxy for hosted deploys.

    Netflix decides the plan country (e.g. US$ 8.99 vs PHP 169/month + free
    trial) from the IP that the GraphQL request comes from. When the backend
    runs on a datacenter (Render), that IP is usually geolocated to the US,
    so the trial country comes out wrong. Point TRIAL_PROXY (or the standard
    HTTPS_PROXY) at a proxy/VPN in your own country to make the hosted site
    behave exactly like the CLI running on your PC.
    """
    for name in ("TRIAL_PROXY", "HTTPS_PROXY", "https_proxy"):
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _snippet(text, limit=300):
    """First chars of Netflix's raw response, for surfacing real failures."""
    return (text or "").strip().replace("\n", " ")[:limit]


async def _send(email, cookie_input=None):
    """Run the two GraphQL posts. Returns (ok, message)."""
    cookies = parse_cookie_input(cookie_input)
    # Use the pasted flwssn when present so the cookie and the GraphQL
    # variables always describe the same guest flow session.
    flwssn = cookies.get("flwssn") or str(uuid.uuid4())
    headers = make_headers()
    # Inject the pasted cookie (cookie-editor-style) into every request.
    headers["Cookie"] = build_cookie_header(cookies, flwssn)
    payload1, payload2 = make_payloads(email, flwssn)

    client_kwargs = {"timeout": 30}
    proxy = _proxy_url()
    if proxy:
        client_kwargs["proxy"] = proxy

    async with httpx.AsyncClient(**client_kwargs) as client:
        resp1 = await client.post(URL, json=payload1, headers=headers)
        if resp1.status_code != 200 or '"errors"' in resp1.text.lower():
            return False, (
                f"Netflix rejected payload 1 (HTTP {resp1.status_code}): "
                f"{_snippet(resp1.text)}"
            )

        resp2 = await client.post(URL, json=payload2, headers=headers)
        if resp2.status_code == 200 and '"errors"' not in resp2.text.lower():
            return True, "Successfully sent 30 days trial for your email."
        return False, (
            f"Second request failed (HTTP {resp2.status_code}): "
            f"{_snippet(resp2.text)}"
        )


def send_trial(email, cookie_input=None):
    """Synchronous wrapper so the web layer can call it easily."""
    email = (email or "").strip()
    if not email or "@" not in email:
        return False, "Invalid email address provided."

    # Normalize/validate the injected cookie early for a friendlier error.
    cookies = parse_cookie_input(cookie_input)
    nfvdid = cookies.get("nfvdid", "")
    if not nfvdid:
        return False, "nfvdid cookie is missing — paste a valid line or JSON."

    try:
        return asyncio.run(_send(email, cookie_input))
    except Exception as exc:  # network/config errors surface to the UI
        return False, f"Error while sending trial: {exc}"


# ---- Web API routes (merged from app.py) --------------------------
@app.route("/")
def home():
    return jsonify(
        {
            "service": "netflix-trial-backend",
            "health": "/healthz",
            "send": "POST /api/send with JSON body {email[, cookie]}",
        }
    )


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/api/send", methods=["POST"])
def api_send():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    # Cookie from the frontend "cookie editor" — bare nfvdid value, a Cookie
    # header line, or the JSON array exported by a cookie editor.
    cookie_input = data.get("cookie") or data.get("nfvdid") or data.get("cookieJson")
    ok, message = send_trial(email, cookie_input)
    return jsonify({"ok": ok, "message": message})


def _build_args():
    parser = argparse.ArgumentParser(
        description="Netflix trial sender — also powers the /api/send web route."
    )
    parser.add_argument(
        "--email",
        help="Email address (default: TRIAL_EMAIL env var, or interactive prompt)",
    )
    parser.add_argument(
        "--cookie",
        help="nfvdid — bare value, Cookie line, or cookie-editor JSON export",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the Cookie header that would be attached; do not call Netflix",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the merged Flask web API on http://127.0.0.1:5000",
    )
    return parser.parse_args()


def _run_cli():
    """Merge the classic standalone flow into this single file."""
    print("\n   [ NETFLIX TRIAL SENDER ]")
    print("          by Lyco\n")

    args = _build_args()

    email = (args.email or os.getenv("TRIAL_EMAIL") or "").strip()
    while not email or "@" not in email:
        email = input("Enter your email address: ").strip()

    cookie_raw = (args.cookie or os.getenv("TRIAL_COOKIE") or "").strip() or None

    if cookie_raw:
        if "nfvdid" not in parse_cookie_input(cookie_raw):
            print(
                "Could not read nfvdid from that input. Paste a bare value, a "
                "Cookie line (nfvdid=...), or the cookie-editor JSON export."
            )
            return 2
        print("Using the nfvdid cookie you provided (injected into every request).")
    elif _load_cookie_file():
        print("Using nfvdid from cookie.txt (used VERBATIM, exactly as saved).")
    else:
        print("No --cookie / cookie.txt — using the built-in default nfvdid.")

    if args.dry_run:
        flwssn = str(uuid.uuid4())
        cookies_used = parse_cookie_input(cookie_raw)
        print("\n[DRY RUN] Cookie header that would be attached:")
        print("  " + build_cookie_header(cookies_used, flwssn))
        print("[DRY RUN] Nothing was sent.")
        return 0

    ok, message = send_trial(email, cookie_raw)
    print(message if ok else "Failed: " + message)
    return 0 if ok else 1


if __name__ == "__main__":
    args = _build_args()
    if args.serve:
        print("Serving the merged website API at http://127.0.0.1:5000")
        app.run(host="0.0.0.0", port=5000)
    else:
        raise SystemExit(_run_cli())
