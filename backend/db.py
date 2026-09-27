"""SQLite access shared by the API routes (main.py) and the agent tools (tools.py)."""

import json
import sqlite3
from pathlib import Path

from models import ProductCard, SizeStock

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]


def get_db(write: bool = False) -> sqlite3.Connection:
    # Read-only by default; only auth and chat-history writes open read-write.
    mode = "rw" if write else "ro"
    conn = sqlite3.connect(f"file:{DB_PATH}?mode={mode}", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def category_for(garment_type: str) -> str:
    """Collapse the 22 messy garment_type values into a few shop categories."""
    g = garment_type.lower()
    if "zip" in g and "quarter" in g:
        return "Quarter-Zips"
    if "jacket" in g or "fleece" in g:
        return "Jackets & Fleece"
    if "hood" in g:
        return "Hoodies"
    if "t-shirt" in g or "long-sleeve" in g:
        return "T-Shirts"
    if "crew" in g or "sweatshirt" in g:
        return "Crewnecks"
    return "Other"


def _size_key(size: str) -> int:
    return SIZE_ORDER.index(size) if size in SIZE_ORDER else len(SIZE_ORDER)


def _inventory_by_product(conn: sqlite3.Connection, ids: list[str] | None = None) -> dict[str, list[SizeStock]]:
    sql = "SELECT product_id, size, quantity FROM inventory"
    params: list[str] = []
    if ids is not None:
        sql += f" WHERE product_id IN ({','.join('?' * len(ids))})"
        params = ids
    stock: dict[str, list[SizeStock]] = {}
    for r in conn.execute(sql, params):
        stock.setdefault(r["product_id"], []).append(SizeStock(size=r["size"], quantity=r["quantity"]))
    for sizes in stock.values():
        sizes.sort(key=lambda s: _size_key(s.size))
    return stock


def _card(row: sqlite3.Row, inventory: list[SizeStock]) -> ProductCard:
    return ProductCard(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        category=category_for(row["garment_type"]),
        description=row["description"],
        colors=json.loads(row["colors"]),
        search_tags=json.loads(row["search_tags"]),
        image_url=f"/media/{row['image_file_path']}",
        price=row["price"],
        inventory=inventory,
        total_stock=sum(s.quantity for s in inventory),
    )


def all_products() -> list[ProductCard]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
        stock = _inventory_by_product(conn)
    return [_card(r, stock.get(r["product_id"], [])) for r in rows]


def products_by_ids(ids: list[str]) -> list[ProductCard]:
    """Return cards for known ids, in the order given; unknown ids are dropped."""
    if not ids:
        return []
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM catalogue WHERE product_id IN ({','.join('?' * len(ids))})", ids
        ).fetchall()
        stock = _inventory_by_product(conn, ids)
    by_id = {r["product_id"]: _card(r, stock.get(r["product_id"], [])) for r in rows}
    return [by_id[i] for i in dict.fromkeys(ids) if i in by_id]


def get_product(product_id: str) -> ProductCard | None:
    found = products_by_ids([product_id])
    return found[0] if found else None


def migrate() -> None:
    """Idempotent schema upgrades, run at API startup. Only ever adds; never drops data.

    chat_messages gains (Problem 8):
      page_json      - on user rows: the page the shopper was on when they sent it
      showcase_json  - on assistant rows: title + filters of the results panel it produced
    plus an index so loading one shopper's recent history stays fast.
    """
    with get_db(write=True) as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(chat_messages)")}
        if "page_json" not in cols:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN page_json TEXT")
        if "showcase_json" not in cols:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN showcase_json TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages (user_id, id)")
