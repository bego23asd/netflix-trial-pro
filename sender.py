import asyncio
import uuid

import httpx

URL = "https://web.prod.cloud.netflix.com/graphql"

NFVDID_VALUE = "BQFmAAEBEDfQY0dAGiJZuocAfFU2CQpAYdUwSM-D1OYmnErF2ElCBLm3CS95c_ywNg2ALWYqpR11S7Q7F8GGn_WlsEleYshSjx9uKQE-KVY35tPLE1ZtgQ%3D%3D"

RECAPTCHA_SITE_KEY = "6LdqW_EqAAAAAO87Fb_kcZfNzs0IqJRcKiJDYpUv"


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


def generate_cookie(flwssn):
    """Build the cookie header purely from known/generated values."""
    return f"nfvdid={NFVDID_VALUE}; flwssn={flwssn}"


async def _send(email):
    """Run the two GraphQL posts. Returns (ok, message)."""
    flwssn = str(uuid.uuid4())
    cookie = generate_cookie(flwssn)
    headers = make_headers()
    headers["Cookie"] = cookie
    payload1, payload2 = make_payloads(email, flwssn)

    async with httpx.AsyncClient(timeout=30) as client:
        resp1 = await client.post(URL, json=payload1, headers=headers)
        if '"errors"' in resp1.text.lower():
            return False, "Netflix rejected the first request (init signup)."

        resp2 = await client.post(URL, json=payload2, headers=headers)
        if resp2.status_code == 200 and '"errors"' not in resp2.text.lower():
            return True, "Successfully sent 30 days trial for your email."
        return False, f"Second request failed (HTTP {resp2.status_code})."


def send_trial(email):
    """Synchronous wrapper so the web layer can call it easily."""
    email = (email or "").strip()
    if not email or "@" not in email:
        return False, "Invalid email address provided."
    return asyncio.run(_send(email))


if __name__ == "__main__":
    email = input("Enter your email address: ").strip()
    ok, message = send_trial(email)
    print(message)