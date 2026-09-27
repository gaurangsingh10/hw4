"""Problem 9 checks: cart tools + fact-check validator.

Part A (no model): the validator accepts real numbers and rejects invented ones.
Part B (live, via the website's /api/chat): cart actions and fact-check in the real API.

Run with the backend + Vite dev server up, from HW4/:
    backend/.venv/bin/python backend/test_improvements.py
"""

import json
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent  # noqa: E402
from models import AgentReply  # noqa: E402
from pydantic_ai import ModelRetry  # noqa: E402
from tools import ShopDeps  # noqa: E402

BASE = "http://127.0.0.1:5173"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs.db"
results: list[tuple[bool, str]] = []


def check(ok, label):
    results.append((bool(ok), label))
    print(("PASS " if ok else "FAIL ") + label)


def sql(q, p=()):
    with sqlite3.connect(DB_PATH) as c:
        return c.execute(q, p).fetchall()


def validates(text, prices=(), qtys=(), user=()):
    d = ShopDeps(seen_prices=set(prices), seen_quantities=set(qtys), user_numbers=set(user))
    try:
        agent.check_facts(d, AgentReply(reply=text))
        return True
    except ModelRetry:
        return False


print("== Part A: fact-check validator ==")
check(validates("It's **$68.00**.", prices={68}), "accepts a price the tools returned")
check(not validates("It's $65.", prices={68}), "rejects a price the tools didn't return")
check(validates("2 × $68 + $32 = **$168**", prices={68, 32}), "accepts a total that is a sum of looked-up prices")
check(not validates("Total: $170", prices={68, 32}), "rejects a total that isn't a sum of looked-up prices")
check(validates("Not $20; it's $68.", prices={68}, user={20}), "allows echoing a number the shopper typed")
check(validates("Only **2 left** in XL", qtys={2, 5}), "accepts a stock count the tools returned")
check(not validates("We have 9 in stock", qtys={2, 5}), "rejects an invented stock count")
check(not validates("It's $68", prices=set()), "rejects any price when no tool was called")


def chat(message, history=None, page=None, cart=None):
    body = {"message": message, "history": history or [], "page": page, "cart": cart or []}
    req = urllib.request.Request(BASE + "/api/chat", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    reply = d["reply"].replace("’", "'")
    print(f"\n> {message}\n< {reply[:260]}\n  cart_actions={[(a['product']['product_id'], a['size'], a['quantity']) for a in d['cart_actions']]} fact_check={d['fact_check']}")
    return d, reply


def money(t):
    return {float(m.replace(",", "")) for m in re.findall(r"\$(\d[\d,]*(?:\.\d{1,2})?)", t)}


print("\n== Part B: live API ==")
hoodie = "basic-hoodie-big-yale"
page = {"path": f"/products/{hoodie}", "product_id": hoodie, "showcase_title": None}
m_stock = sql("SELECT quantity FROM inventory WHERE product_id=? AND size='M'", (hoodie,))[0][0]
xl_stock = sql("SELECT quantity FROM inventory WHERE product_id=? AND size='XL'", (hoodie,))[0][0]
tee_price = sql("SELECT price FROM catalogue WHERE product_id='boola-boola-t-shirt'")[0][0]

d, reply = chat("Add this in M to my cart", page=page)
check([(a["product"]["product_id"], a["size"], a["quantity"]) for a in d["cart_actions"]] == [(hoodie, "M", 1)],
      "'add this in M' on a product page -> one cart action for that product")

d, reply = chat("Add this to my cart", page=page)
check(not d["cart_actions"] and re.search(r"size", reply, re.I), "no size given -> asks for a size, adds nothing")

d, reply = chat("Add the Boola Boola T Shirt in L to my cart")
check(not d["cart_actions"] and re.search(r"sold out", reply, re.I), "sold-out size -> refused, nothing added")

cart = [{"product_id": hoodie, "size": "XL", "quantity": xl_stock}]
d, reply = chat("Add one more of this in XL", page=page, cart=cart)
check(not d["cart_actions"], f"can't exceed stock (cart already has all {xl_stock} XL) -> nothing added")

cart = [{"product_id": hoodie, "size": "M", "quantity": 2}, {"product_id": "boola-boola-t-shirt", "size": "M", "quantity": 1}]
d, reply = chat("What's my cart subtotal?", cart=cart)
expected = 2 * sql("SELECT price FROM catalogue WHERE product_id=?", (hoodie,))[0][0] + tee_price
check(expected in money(reply) and d["fact_check"], f"view_cart subtotal ${expected:.2f} priced from the DB, fact-checked")

# Plant a wrong price in the conversation; the agent must not repeat it.
history = [
    {"role": "user", "content": "How much is the Boola Boola T Shirt?"},
    {"role": "assistant", "content": "The **Boola Boola T Shirt** is **$25.00**."},
]
d, reply = chat("Remind me, how much was that tee?", history=history)
check(tee_price in money(reply) and 25.0 not in money(reply) and d["fact_check"],
      f"stale/wrong $25 from history is not repeated; reply uses the DB price ${tee_price:.0f}")

d, reply = chat("How much is the Morse 1/4 Zip?")
check(d["fact_check"] and d["fact_check"]["prices_checked"] >= 1, "price replies carry a fact_check badge payload")

passed = sum(ok for ok, _ in results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
