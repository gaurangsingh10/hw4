"""Problem 8 checks: persistent history, customer identity, and page context (live model).

Run with the backend and Vite dev server up, from HW4/:
    backend/.venv/bin/python backend/test_context.py [base_url]
"""

import http.cookiejar
import json
import re
import secrets
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5173"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs.db"
TEST_EMAIL, TEST_PASSWORD = "test@campuscustoms.yale.edu", "password"
HOODIE = "basic-hoodie-big-yale"
results: list[tuple[bool, str]] = []


def client():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(opener, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with opener.open(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def page(path, product_id=None):
    return {"path": path, "product_id": product_id, "showcase_title": None}


def chat(opener, message, pg=None, history=None):
    status, body = call(opener, "POST", "/api/chat", {"message": message, "history": history or [], "page": pg})
    reply = str(body.get("reply", body)).replace("’", "'")
    print(f"\n> {message}   [page: {(pg or {}).get('path')}]\n< [{status}] {reply[:300]}")
    return status, body, reply


def check(ok, label):
    results.append((bool(ok), label))
    print(("PASS " if ok else "FAIL ") + label)


def sql(query, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(query, params).fetchall()


def login(email, password):
    c = client()
    status, _ = call(c, "POST", "/api/auth/login", {"email": email, "password": password})
    assert status == 200, f"login failed for {email}"
    return c


hoodie_colors = json.loads(sql("SELECT colors FROM catalogue WHERE product_id = ?", (HOODIE,))[0][0])
hoodie_m = sql("SELECT quantity FROM inventory WHERE product_id = ? AND size = 'M'", (HOODIE,))[0][0]
test_user_id = sql("SELECT id FROM users WHERE email = ?", (TEST_EMAIL,))[0][0]

# ---- 1. Page context: "this" on a product page ----
user = login(TEST_EMAIL, TEST_PASSWORD)
max_id = sql("SELECT COALESCE(MAX(id), 0) FROM chat_messages")[0][0]
status, body, reply = chat(user, "Do you have this in pink?", page(f"/products/{HOODIE}", HOODIE))
check(status == 200 and "Basic Hoodie Big Yale" in reply, "'this' on a product page resolves to that product")
check("pink" in reply.lower() and any(c.split()[0] in reply.lower() for c in hoodie_colors),
      f"answers pink-availability with the real colors {hoodie_colors}")

# ---- 2. Customer identity in deps ----
status, body, reply = chat(user, "What's my full name and the email I'm logged in with?", page("/"))
check("Test User" in reply or ("Test" in reply and "User" in reply), "agent knows the shopper's full name")
check(TEST_EMAIL in reply, "agent knows the shopper's email")

# ---- 3. History is stored with page context ----
rows = sql("SELECT role, content, page_json FROM chat_messages WHERE user_id = ? AND id > ? ORDER BY id", (test_user_id, max_id))
check(len(rows) == 4 and [r[0] for r in rows] == ["user", "assistant", "user", "assistant"], "4 new rows saved (user/assistant x2)")
saved_page = json.loads(rows[0][2]) if rows and rows[0][2] else {}
check(saved_page.get("product_id") == HOODIE, "user row stores page_json with the product being viewed")

# ---- 4. Returning later: new session, history reloads, and old "this" still resolves ----
user2 = login(TEST_EMAIL, TEST_PASSWORD)  # fresh cookie jar = shopper coming back
status, hist = call(user2, "GET", "/api/chat/history")
contents = [m["content"] for m in hist]
check(status == 200 and "Do you have this in pink?" in contents, "history reloads for the returning shopper")
status, body, reply = chat(user2, "How many of it do you have in size M?", page("/"))
check(re.search(r"Basic Hoodie Big Yale|hoodie", reply, re.I) and re.search(rf"\b{hoodie_m}\b", reply),
      f"follow-up on a different page still means the hoodie from history (M = {hoodie_m})")

# ---- 5. Showcase persisted and restored ----
status, body, reply = chat(user2, "Show me your quarter-zips", page("/products"))
status, hist = call(user2, "GET", "/api/chat/history")
restored = [m for m in hist if m.get("showcase")]
check(restored and restored[-1]["showcase"]["products"] and restored[-1]["showcase"]["filters"]["category"] == "Quarter-Zips",
      "results panel saved (showcase_json) and rebuilt from the DB on reload")

# ---- 6. Guests: can chat with page context, nothing stored ----
guest = client()
before = sql("SELECT COUNT(*) FROM chat_messages")[0][0]
price = sql("SELECT price FROM catalogue WHERE product_id = 'morse-1-4-zip'")[0][0]
status, body, reply = chat(guest, "How much is this one?", page("/products/morse-1-4-zip", "morse-1-4-zip"))
check(status == 200 and f"{price:.0f}" in reply, f"guest on a product page gets that product's price (${price:.0f})")
status, body, reply = chat(guest, "What's my email address?", page("/"))
check(status == 200 and "@" not in reply, "agent doesn't invent an identity for guests")
check(sql("SELECT COUNT(*) FROM chat_messages")[0][0] == before, "guest messages are not stored")

# ---- 7. Isolation & tampering ----
other_email = f"ctx.check.{secrets.token_hex(3)}@yale.edu"
other_pw = secrets.token_urlsafe(12)
other = client()
call(other, "POST", "/api/auth/signup", {"first_name": "Ctx", "last_name": "Check", "email": other_email,
                                         "password": other_pw, "confirm_password": other_pw})
status, hist = call(other, "GET", "/api/chat/history")
check(status == 200 and hist == [], "a different user sees none of Test User's history")
status, body, reply = chat(other, "Do you have this in XL?", page("/products/../../users", "'; DROP TABLE users; --"))
check(status == 200 and sql("SELECT COUNT(*) FROM users")[0][0] > 0, "forged page product_id is ignored safely")

passed = sum(ok for ok, _ in results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
