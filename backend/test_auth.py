"""End-to-end check of the auth flow against the running dev servers.

Run with the backend and Vite dev server up:
    backend/.venv/bin/python backend/test_auth.py [base_url]

Goes through the Vite proxy (default http://127.0.0.1:5173) so cookies behave
exactly like they do in the browser. Creates one new account per run.
"""

import http.cookiejar
import json
import secrets
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5173"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs.db"
SEED_EMAIL, SEED_PASSWORD = "test@campuscustoms.yale.edu", "password"

results: list[tuple[bool, str]] = []


def client():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar


def call(opener, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with opener.open(req) as r:
            return r.status, json.loads(r.read()), r.headers.get_all("Set-Cookie") or []
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), []


def check(ok, label):
    results.append((bool(ok), label))
    print(("PASS " if ok else "FAIL ") + label)


def stored_hash(email):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()
    return row[0] if row else None


# 1. Seed test user
c, _ = client()
status, user, cookies = call(c, "POST", "/api/auth/login", {"email": SEED_EMAIL, "password": SEED_PASSWORD})
check(status == 200 and user.get("first_name") == "Test", "seed test user can log in")
check(any("HttpOnly" in h for h in cookies), "session cookie is HttpOnly")
check("password_hash" not in user, "login response never includes password_hash")
status, me, _ = call(c, "GET", "/api/auth/me")
check(status == 200 and me["email"] == SEED_EMAIL, "/me returns the logged-in seed user")
check(stored_hash(SEED_EMAIL).startswith("pbkdf2_sha256$600000$"), "legacy seed hash upgraded to 600k iterations")
call(c, "POST", "/api/auth/logout")
status, _, _ = call(c, "GET", "/api/auth/me")
check(status == 401, "logout ends the session")

# 2. Wrong password / unknown email give the same generic error
status, err, _ = call(client()[0], "POST", "/api/auth/login", {"email": SEED_EMAIL, "password": "wrong-password"})
status2, err2, _ = call(client()[0], "POST", "/api/auth/login", {"email": "nobody@yale.edu", "password": "whatever1"})
check(status == status2 == 401 and err == err2, "wrong password and unknown email return identical 401s")

# 3. Brand-new account
email = f"new.bulldog.{secrets.token_hex(3)}@yale.edu"
password = secrets.token_urlsafe(12)
signup = {"first_name": "New", "last_name": "Bulldog", "email": email, "password": password}

status, err, _ = call(client()[0], "POST", "/api/auth/signup", {**signup, "confirm_password": password + "x"})
check(status == 400 and "match" in err["detail"], "signup rejects mismatched confirm password")
status, err, _ = call(client()[0], "POST", "/api/auth/signup", {**signup, "password": "short", "confirm_password": "short"})
check(status == 400, "signup rejects passwords under 8 characters")

c, _ = client()
status, user, _ = call(c, "POST", "/api/auth/signup", {**signup, "confirm_password": password})
check(status == 201 and user["name"] == "New Bulldog", "new account created")
status, me, _ = call(c, "GET", "/api/auth/me")
check(status == 200 and me["email"] == email, "new account is logged in right after signup")

h = stored_hash(email)
check(h and password not in h and h.startswith("pbkdf2_sha256$600000$"), "new password stored only as a salted PBKDF2 hash")

status, _, _ = call(client()[0], "POST", "/api/auth/signup", {**signup, "email": email.upper(), "confirm_password": password})
check(status == 409, "duplicate email (any case) is rejected")

c, _ = client()
status, user, _ = call(c, "POST", "/api/auth/login", {"email": email, "password": password})
check(status == 200 and user["email"] == email, "new account can log back in")

# 4. Tampered cookie is rejected
c, jar = client()
call(c, "POST", "/api/auth/login", {"email": email, "password": password})
for cookie in jar:
    cookie.value = cookie.value[:-2] + ("AA" if not cookie.value.endswith("AA") else "BB")
status, _, _ = call(c, "GET", "/api/auth/me")
check(status == 401, "tampered session cookie is rejected")

passed = sum(ok for ok, _ in results)
print(f"\n{passed}/{len(results)} checks passed (new test account: {email})")
sys.exit(0 if passed == len(results) else 1)
