"""Campus Customs API.

Problem 3: serves the catalogue, inventory, and product images from
data/campus_customs.db.
Problem 4: create-account / log-in with hashed passwords and signed cookies.
Problem 5: /api/chat runs the PydanticAI shopping agent (see agent.py).
Problem 7: browse requests return a `showcase` of search results for the page.
Problem 8: logged-in chat history persisted/reloaded; customer + page context in agent deps.

Run from the backend/ folder:
    uvicorn main:app --reload --port 8000
"""

import json
import logging
import re
import sqlite3

from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agent
import auth
import db
from db import get_db
from models import (
    ChatHistoryMessage,
    ChatRequest,
    ChatResponse,
    ChatTurn,
    CustomerContext,
    PageContext,
    ProductCard,
    Showcase,
)
from tools import ShopDeps

log = logging.getLogger("campus_customs")
CHAT_HISTORY_TURNS = 20  # messages of prior context given to the agent

app = FastAPI(title="Campus Customs API")
db.migrate()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Product photos: data/products/<file>.jpg -> /media/products/<file>.jpg
app.mount("/media", StaticFiles(directory=db.DATA_DIR), name="media")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/products")
def list_products() -> list[ProductCard]:
    return db.all_products()


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> ProductCard:
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ---------- Auth ----------

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def public_user(row: sqlite3.Row) -> dict:
    # Never include password_hash in anything sent to the browser (or the chatbot).
    return {
        "id": row["id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "name": row["name"],
        "email": row["email"],
    }


def set_session(response: Response, user_id: int) -> None:
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.create_session_token(user_id),
        max_age=auth.SESSION_TTL_SECONDS,
        httponly=True,  # not readable from JavaScript
        samesite="lax",
        # secure=True should be enabled when served over HTTPS in production.
    )


def current_user(session: str | None) -> dict | None:
    user_id = auth.read_session_token(session)
    if user_id is None:
        return None
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(row) if row else None


@app.post("/api/auth/signup", status_code=201)
def signup(req: SignupRequest, response: Response):
    first, last = req.first_name.strip(), req.last_name.strip()
    email = req.email.strip().lower()
    if not first or not last:
        raise HTTPException(400, "First and last name are required.")
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Please enter a valid email address.")
    if len(req.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(400, f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if req.password != req.confirm_password:
        raise HTTPException(400, "Passwords do not match.")

    with get_db(write=True) as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(409, "An account with that email already exists.")
        cur = conn.execute(
            "INSERT INTO users (name, first_name, last_name, email, password_hash) VALUES (?, ?, ?, ?, ?)",
            (f"{first} {last}", first, last, email, auth.hash_password(req.password)),
        )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()

    set_session(response, row["id"])
    return public_user(row)


@app.post("/api/auth/login")
def login(req: LoginRequest, response: Response):
    email = req.email.strip().lower()
    if auth.is_locked_out(email):
        raise HTTPException(429, "Too many failed attempts. Please try again in 15 minutes.")

    with get_db(write=True) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        stored = row["password_hash"] if row else auth.DUMMY_HASH
        if not auth.verify_password(req.password, stored) or row is None:
            auth.record_failure(email)
            # Same message whether the email or the password was wrong.
            raise HTTPException(401, "Invalid email or password.")
        if auth.needs_rehash(stored):
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (auth.hash_password(req.password), row["id"]),
            )

    auth.clear_failures(email)
    set_session(response, row["id"])
    return public_user(row)


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/auth/me")
def me(cc_session: str | None = Cookie(default=None)):
    user = current_user(cc_session)
    if user is None:
        raise HTTPException(401, "Not logged in.")
    return user


# ---------- Chat ----------
#
# Logged-in history lives in the existing chat_messages table (one row per message):
#   user rows:      content + page_json (where they were)
#   assistant rows: content + products_json (chat cards) + showcase_json (results panel)
# Guests: nothing is stored server-side.

def load_history(user_id: int, limit: int = CHAT_HISTORY_TURNS) -> list[sqlite3.Row]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT role, content, products_json, page_json, showcase_json, created_at
               FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return list(reversed(rows))


def history_for_agent(rows: list[sqlite3.Row]) -> list[ChatTurn]:
    """Replay saved turns, noting which product page each user message was sent from,
    so "this one" in an earlier message still resolves correctly."""
    turns = []
    for r in rows:
        content = r["content"]
        if r["role"] == "user" and r["page_json"]:
            page = PageContext.model_validate_json(r["page_json"])
            product = db.get_product(page.product_id) if page.product_id else None
            if product:
                content = f"[sent while viewing: {product.name} ({product.product_id})]\n{content}"
        turns.append(ChatTurn(role=r["role"], content=content[:4000]))
    return turns


def save_turn(user_id: int, message: str, page: PageContext | None, response: ChatResponse) -> None:
    products_json = json.dumps([p.model_dump() for p in response.products])
    showcase_json = (
        Showcase(title=response.showcase.title, filters=response.showcase.filters).model_dump_json()
        if response.showcase
        else None
    )
    with get_db(write=True) as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, page_json) VALUES (?, 'user', ?, ?)",
            (user_id, message, page.model_dump_json() if page else None),
        )
        conn.execute(
            """INSERT INTO chat_messages (user_id, role, content, products_json, showcase_json)
               VALUES (?, 'assistant', ?, ?, ?)""",
            (user_id, response.reply, products_json, showcase_json),
        )


def build_deps(user: dict | None, page: PageContext | None) -> ShopDeps:
    """Assemble the agent's per-turn context. Identity comes only from the session cookie;
    the page's product_id is client-supplied, so it's only used if it exists in the DB."""
    customer = (
        CustomerContext(first_name=user["first_name"], last_name=user["last_name"], email=user["email"])
        if user
        else None
    )
    current_product = db.get_product(page.product_id) if page and page.product_id else None
    return ShopDeps(customer=customer, page=page, current_product=current_product)


def attach_cart(deps: ShopDeps, cart: list) -> ShopDeps:
    """The cart is client-side; tools re-price it from the DB, so only ids/sizes/quantities are used."""
    deps.cart = list(cart)
    return deps


@app.post("/api/chat")
async def chat(req: ChatRequest, cc_session: str | None = Cookie(default=None)) -> ChatResponse:
    user = current_user(cc_session)
    message = req.message.strip()
    if not message:
        raise HTTPException(400, "Message is empty.")

    if user:
        # Logged in: history comes from the DB (the client can't forge it).
        history = history_for_agent(load_history(user["id"]))
    else:
        # Guest: nothing is stored server-side, so the widget sends recent turns.
        history = req.history[-CHAT_HISTORY_TURNS:]

    try:
        response = await agent.run_chat(message, history, attach_cart(build_deps(user, req.page), req.cart))
    except agent.AgentUnavailable as e:
        log.error("Agent unavailable: %s", e)
        raise HTTPException(503, "The shopping assistant isn't configured yet. Please try again later.")
    except Exception:
        log.exception("Agent run failed")
        raise HTTPException(502, "The shopping assistant hit a snag. Please try again in a moment.")

    if user:
        save_turn(user["id"], message, req.page, response)
    return response


@app.get("/api/chat/history")
def chat_history(cc_session: str | None = Cookie(default=None)) -> list[ChatHistoryMessage]:
    """The logged-in shopper's own recent messages, so the widget can restore the conversation.

    Cards and results panels are rebuilt from the DB, so prices and stock are current."""
    user = current_user(cc_session)
    if user is None:
        return []
    messages = []
    for r in load_history(user["id"], limit=50):
        cards = []
        if r["products_json"]:
            ids = [p.get("product_id") for p in json.loads(r["products_json"]) if isinstance(p, dict)]
            cards = db.products_by_ids([i for i in ids if i])
        showcase = None
        if r["showcase_json"]:
            saved = Showcase.model_validate_json(r["showcase_json"])
            showcase = agent.build_showcase(saved, ShopDeps())
        messages.append(
            ChatHistoryMessage(
                role=r["role"], content=r["content"], products=cards, showcase=showcase, created_at=r["created_at"]
            )
        )
    return messages
