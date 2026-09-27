"""Checks for the Problem 6 lookup tools.

Part A (no model): every tool result is compared with raw SQL for all products.
Part B (live model): the agent must call the right tool and quote the DB's numbers.

Run from HW4/ (backend server not needed):
    backend/.venv/bin/python backend/test_tools.py          # A + B
    backend/.venv/bin/python backend/test_tools.py --offline  # A only
"""

import asyncio
import re
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tools  # noqa: E402
from models import LookupFailure, PriceInfo, ProductDescription, StockInfo  # noqa: E402

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs.db"
results: list[tuple[bool, str]] = []


def check(ok, label):
    results.append((bool(ok), label))
    print(("PASS " if ok else "FAIL ") + label)


def sql(query, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(query, params).fetchall()


def ctx():
    return SimpleNamespace(deps=tools.ShopDeps())


# ---------------- Part A: tools vs. raw SQL ----------------
print("== Part A: tool results vs database ==")
catalogue = sql("SELECT product_id, name, price, description FROM catalogue")
stock = {}
for pid, size, qty in sql("SELECT product_id, size, quantity FROM inventory"):
    stock.setdefault(pid, {})[size] = qty

price_ok = desc_ok = stock_ok = by_name_ok = True
for pid, name, price, description in catalogue:
    p = tools.get_price(ctx(), pid)
    price_ok &= isinstance(p, PriceInfo) and p.price == price
    d = tools.get_product_description(ctx(), pid)
    desc_ok &= isinstance(d, ProductDescription) and d.description == description
    s = tools.get_stock(ctx(), pid)
    stock_ok &= (
        isinstance(s, StockInfo)
        and {x.size: x.quantity for x in s.sizes} == stock[pid]
        and s.total_in_stock == sum(stock[pid].values())
        and set(s.sold_out_sizes) == {k for k, v in stock[pid].items() if v == 0}
        and all((x.status == "sold_out") == (x.quantity == 0) for x in s.sizes)
    )
    by_name_ok &= getattr(tools.get_price(ctx(), name), "product_id", None) == pid
check(price_ok, f"get_price matches catalogue.price for all {len(catalogue)} products")
check(desc_ok, "get_product_description matches catalogue.description for all products")
check(stock_ok, "get_stock matches inventory (qty, totals, sold-out, status) for all products")
check(by_name_ok, "every product resolves by exact name as well as product_id")

pid, size, qty = sql("SELECT product_id, size, quantity FROM inventory WHERE quantity BETWEEN 1 AND 3 LIMIT 1")[0]
s = tools.get_stock(ctx(), pid, size)
check(isinstance(s, StockInfo) and len(s.sizes) == 1 and s.sizes[0].quantity == qty and s.sizes[0].status == "low_stock",
      f"get_stock(size={size}) returns only that size, flagged low_stock")
pid0, size0 = sql("SELECT product_id, size FROM inventory WHERE quantity = 0 LIMIT 1")[0]
s = tools.get_stock(ctx(), pid0, size0)
check(isinstance(s, StockInfo) and s.sizes[0].status == "sold_out" and s.sizes[0].quantity == 0,
      f"sold-out size ({pid0} {size0}) reported as sold_out")
s = tools.get_stock(ctx(), "basic-hoodie-big-yale", "medium")
check(isinstance(s, StockInfo) and s.requested_size == "M", "size words are normalized ('medium' -> M)")
s = tools.get_stock(ctx(), "basic-hoodie-big-yale", "XXXL")
check(isinstance(s, LookupFailure) and "XXL" in s.valid_sizes, "unknown size XXXL returns an error with valid_sizes")
r = tools.get_price(ctx(), "Saybrook")
check(isinstance(r, LookupFailure) and len(r.did_you_mean) >= 2, "ambiguous name ('Saybrook') asks the shopper to choose")
r = tools.get_price(ctx(), "Lamborghini racing jacket")
check(isinstance(r, LookupFailure) and "No product is named exactly" in r.error,
      "non-existent product is flagged 'no exact match' (with only partial suggestions), not resolved")
r = tools.get_price(ctx(), "zzzz qqqq")
check(isinstance(r, LookupFailure) and not r.did_you_mean, "gibberish product returns 'we don't carry it' with no suggestions")

if "--offline" in sys.argv:
    passed = sum(ok for ok, _ in results)
    print(f"\n{passed}/{len(results)} checks passed")
    sys.exit(0 if passed == len(results) else 1)


# ---------------- Part B: live agent ----------------
print("\n== Part B: live agent uses the tools and quotes the DB ==")
import agent  # noqa: E402


all_replies: list[str] = []


async def ask(question):
    deps = tools.ShopDeps()
    result = await agent.get_agent().run(question, deps=deps, usage_limits=agent.USAGE_LIMITS)
    reply = result.output.reply.replace("’", "'")
    all_replies.append(reply)
    print(f"\n> {question}\n  tools: {deps.tool_calls}\n< {reply[:350]}")
    return reply, deps.tool_calls


def money(text):
    return {float(m.replace(",", "")) for m in re.findall(r"\$(\d[\d,]*(?:\.\d{1,2})?)", text)}


async def live():
    hoodie_price = sql("SELECT price FROM catalogue WHERE product_id = 'basic-hoodie-big-yale'")[0][0]
    tee_price = sql("SELECT price FROM catalogue WHERE product_id = 'boola-boola-t-shirt'")[0][0]
    real_prices = {row[0] for row in sql("SELECT DISTINCT price FROM catalogue")}
    xl_qty = sql("SELECT quantity FROM inventory WHERE product_id = 'basic-hoodie-big-yale' AND size = 'XL'")[0][0]

    reply, used = await ask("How much is the Basic Hoodie Big Yale?")
    check("get_price" in used and money(reply) == {hoodie_price}, f"price question -> get_price, quotes ${hoodie_price:.0f}")

    reply, used = await ask("I heard the Basic Hoodie Big Yale is only $20, right?")
    check("get_price" in used and hoodie_price in money(reply), "corrects a wrong price from the shopper using the DB")

    reply, used = await ask("How many Basic Hoodie Big Yale do you have left in XL?")
    check("get_stock" in used and re.search(rf"\b{xl_qty}\b", reply), f"stock-by-size question -> get_stock, says {xl_qty}")

    name0 = sql("SELECT name FROM catalogue WHERE product_id = ?", (pid0,))[0][0]
    reply, used = await ask(f"Is the {name0} available in size {size0}?")
    check("get_stock" in used and re.search(r"sold out|out of stock", reply, re.I), f"sold-out size clearly reported ({name0} {size0})")

    reply, used = await ask("Do you have the Basic Hoodie Big Yale in XXXL?")
    check("get_stock" in used and re.search(r"XXL", reply) and re.search(r"(don't|do not|isn't|not)\b.*(offer|come|make|carry|available)", reply, re.I),
          "unsupported size explained with valid sizes")

    reply, used = await ask("What does the Morse 1/4 Zip look like?")
    desc = sql("SELECT description FROM catalogue WHERE product_id = 'morse-1-4-zip'")[0][0]
    check("get_product_description" in used and any(w in reply.lower() for w in _tokens_of(desc)), "description question -> get_product_description")

    reply, used = await ask("How much is the Yale Lamborghini racing jacket?")
    check(re.search(r"couldn't find|could not find|don't carry|do not carry|don't have", reply, re.I)
          and money(reply) <= real_prices, "says we don't carry it; any prices shown are real catalogue prices")

    reply, used = await ask("What would 2 Basic Hoodie Big Yale plus 1 Boola Boola T Shirt cost in total?")
    total = 2 * hoodie_price + tee_price
    check(used.count("get_price") >= 2 and total in money(reply), f"multi-item total computed from DB prices (${total:.0f})")

    allowed = real_prices | {total, 2 * hoodie_price, 20.0}  # 20 = the shopper's wrong claim, echoed back
    invented = set().union(*(money(r) for r in all_replies)) - allowed
    check(not invented, f"no invented dollar amounts in any reply {sorted(invented) or ''}")


def _tokens_of(text):
    return {w for w in re.findall(r"[a-z]{5,}", text.lower())}


asyncio.run(live())
passed = sum(ok for ok, _ in results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
