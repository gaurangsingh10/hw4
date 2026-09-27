"""Tools the Campus Customs agent can call.

Every tool is read-only and returns catalogue/inventory data straight from
data/campus_customs.db. Nothing here can see password hashes or other
customers, or write to the database.

Discovery:  search_products, list_categories
Lookups:    get_product_description, get_price, get_stock   (Problem 6)
Context:    get_my_account, get_current_page                (Problem 8)
Cart:       add_to_cart, view_cart                          (Problem 9)

Every price/quantity a tool returns is also recorded in ShopDeps.seen_prices /
seen_quantities, which the fact-check in agent.py compares the final reply against.
"""

import re
from dataclasses import dataclass, field

from pydantic_ai import RunContext

import db
from models import (
    FactCheck,
    CartAction,
    CartActionResult,
    CartLine,
    CartLineView,
    CartView,
    Category,
    CustomerContext,
    LookupFailure,
    PageContext,
    PageInfo,
    PriceInfo,
    ProductCard,
    ProductDescription,
    ProductSummary,
    SearchFilters,
    SearchResults,
    SizeAvailability,
    StockInfo,
    stock_status,
)

MAX_SEARCH_RESULTS = 8
MAX_SUGGESTIONS = 5
TOKEN_RE = re.compile(r"[a-z0-9]+")
# Words that carry no signal in a shopper's query.
STOPWORDS = {
    "a", "an", "and", "any", "do", "for", "have", "i", "in", "is", "me", "my", "of",
    "show", "some", "the", "to", "want", "with", "you", "your", "yale", "shirt", "shirts",
}
SIZE_ALIASES = {
    "XS": "XS", "XSMALL": "XS", "EXTRASMALL": "XS",
    "S": "S", "SM": "S", "SMALL": "S",
    "M": "M", "MD": "M", "MED": "M", "MEDIUM": "M",
    "L": "L", "LG": "L", "LARGE": "L",
    "XL": "XL", "XLARGE": "XL", "EXTRALARGE": "XL",
    "XXL": "XXL", "2XL": "XXL", "XXLARGE": "XXL", "2XLARGE": "XXL",
}


@dataclass
class ShopDeps:
    """Per-request context handed to the agent and its tools.

    Built by main.py for every chat turn. `customer` comes from the session cookie
    (never from the request body); `page` comes from the website and is only trusted
    after `current_product` has been verified against the database.
    """

    customer: CustomerContext | None = None  # None for guests
    page: PageContext | None = None
    current_product: ProductCard | None = None  # verified product on screen, if any
    cart: list[CartLine] = field(default_factory=list)  # shopper's cart as sent by the site
    cart_actions: list[CartAction] = field(default_factory=list)  # items added this turn
    seen_product_ids: set[str] = field(default_factory=set)
    # Numbers the tools returned this turn: the only ones the reply may quote.
    seen_prices: set[float] = field(default_factory=set)
    seen_quantities: set[int] = field(default_factory=set)
    user_numbers: set[float] = field(default_factory=set)  # numbers the shopper typed (may be echoed)
    fact_check_failures: int = 0
    fact_check: "FactCheck | None" = None
    tool_calls: list[str] = field(default_factory=list)  # audit trail for tests/logging
    last_search: SearchFilters | None = None  # fallback filters for the showcase


# ---------- helpers ----------

def _tokens(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS}


def _summary(p: ProductCard, deps: "ShopDeps | None" = None) -> ProductSummary:
    if deps is not None:
        deps.seen_prices.add(p.price)
    return ProductSummary(
        product_id=p.product_id,
        name=p.name,
        category=p.category,
        price=p.price,
        colors=p.colors,
        sizes_in_stock=[s.size for s in p.inventory if s.quantity > 0],
    )


def _score(q_tokens: set[str], p: ProductCard) -> int:
    name_t = _tokens(p.name)
    tag_t = _tokens(" ".join(p.search_tags))
    other_t = _tokens(" ".join([p.description, p.garment_type, p.category, *p.colors]))
    return 3 * len(q_tokens & name_t) + 2 * len(q_tokens & tag_t) + len(q_tokens & other_t)


def normalize_size(size: str) -> str | None:
    return SIZE_ALIASES.get(re.sub(r"[^A-Z0-9]", "", size.upper()))


def resolve_product(ctx: RunContext[ShopDeps], product: str) -> ProductCard | LookupFailure:
    """Turn a product_id or product name into exactly one product, or explain why not.

    Never guesses between several candidates: ambiguous input returns suggestions.
    """
    key = product.strip()
    found = db.get_product(key)  # exact product_id
    if found is None:
        catalogue = db.all_products()
        # Exact name match, ignoring case and punctuation ("Morse 1/4 Zip" == "Morse 1 4 Zip").
        norm = " ".join(TOKEN_RE.findall(key.lower()))
        found = next((p for p in catalogue if " ".join(TOKEN_RE.findall(p.name.lower())) == norm), None)
        if found is None:
            q = _tokens(key)
            ranked = sorted(
                ((s, p) for p in catalogue if q and (s := _score(q, p)) > 0),
                key=lambda sp: (-sp[0], sp[1].name),
            )
            if len(ranked) == 1:
                found = ranked[0][1]
            else:
                suggestions = [_summary(p, ctx.deps) for _, p in ranked[:MAX_SUGGESTIONS]]
                ctx.deps.seen_product_ids.update(s.product_id for s in suggestions)
                return LookupFailure(
                    error=(
                        f"No product is named exactly '{product}'. These are the closest partial matches: "
                        "if one is clearly what the shopper meant, confirm with them first; otherwise say "
                        "we don't carry it. Don't make up details."
                        if ranked
                        else f"No product matches '{product}'. We don't carry it; don't make up details."
                    ),
                    did_you_mean=suggestions,
                )
    ctx.deps.seen_product_ids.add(found.product_id)
    return found


# ---------- discovery tools ----------

def run_search(filters: SearchFilters) -> tuple[int, list[ProductCard]]:
    """Deterministic catalogue search shared by the tool and the showcase (same input -> same output)."""
    q_tokens = _tokens(filters.query or "")
    color_l = filters.color.lower().strip() if filters.color else None
    size_n = normalize_size(filters.size) if filters.size else None
    scored: list[tuple[int, ProductCard]] = []

    for p in db.all_products():
        if filters.category and p.category.lower() != filters.category.lower():
            continue
        if filters.max_price is not None and p.price > filters.max_price:
            continue
        if color_l and not any(color_l in c.lower() for c in p.colors):
            continue
        if size_n and not any(s.size == size_n and s.quantity > 0 for s in p.inventory):
            continue
        score = _score(q_tokens, p) if q_tokens else 0
        if q_tokens and score == 0:
            continue
        scored.append((score, p))

    scored.sort(key=lambda sp: (-sp[0], sp[1].name))
    return len(scored), [p for _, p in scored]


def search_products(
    ctx: RunContext[ShopDeps],
    query: str | None = None,
    category: Category | None = None,
    color: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
) -> SearchResults:
    """Search the Campus Customs catalogue to find products. Use it to discover what we carry.

    Args:
        query: Free-text keywords, e.g. "saybrook", "hockey hoodie", "harvard game".
        category: One of "T-Shirts", "Crewnecks", "Hoodies", "Quarter-Zips", "Jackets & Fleece".
        color: A color to filter by, e.g. "navy", "gray", "white".
        max_price: Only return products at or below this price in USD.
        size: Only return products with this size in stock (XS, S, M, L, XL, XXL).

    Returns the total number of matches and up to 8 of them, best first. If you set `showcase`
    with these same filters, the website shows every match as cards on the page.
    """
    ctx.deps.tool_calls.append("search_products")
    filters = SearchFilters(query=query, category=category, color=color, max_price=max_price, size=size)
    ctx.deps.last_search = filters
    total, matches = run_search(filters)
    results = [_summary(p, ctx.deps) for p in matches[:MAX_SEARCH_RESULTS]]
    ctx.deps.seen_quantities.add(total)
    ctx.deps.seen_product_ids.update(r.product_id for r in results)
    return SearchResults(total_matches=total, showing=results)


def list_categories(ctx: RunContext[ShopDeps]) -> dict[str, int]:
    """List the shop's product categories and how many products are in each."""
    ctx.deps.tool_calls.append("list_categories")
    counts: dict[str, int] = {}
    for p in db.all_products():
        counts[p.category] = counts.get(p.category, 0) + 1
    return dict(sorted(counts.items()))


# ---------- lookup tools (database is the source of truth) ----------

def get_product_description(ctx: RunContext[ShopDeps], product: str) -> ProductDescription | LookupFailure:
    """Look up what a product is: its full description, garment type, and available colors.

    Use for "what does it look like / what is it / what colors" questions.

    Args:
        product: The product_id (preferred, from search results) or the product's name.
    """
    ctx.deps.tool_calls.append("get_product_description")
    p = resolve_product(ctx, product)
    if isinstance(p, LookupFailure):
        return p
    return ProductDescription(
        product_id=p.product_id,
        name=p.name,
        category=p.category,
        garment_type=p.garment_type,
        description=p.description,
        colors=p.colors,
    )


def get_price(ctx: RunContext[ShopDeps], product: str) -> PriceInfo | LookupFailure:
    """Look up a product's current price from the database. Call this for every price question.

    Args:
        product: The product_id (preferred, from search results) or the product's name.
    """
    ctx.deps.tool_calls.append("get_price")
    p = resolve_product(ctx, product)
    if isinstance(p, LookupFailure):
        return p
    ctx.deps.seen_prices.add(p.price)
    return PriceInfo(product_id=p.product_id, name=p.name, price=p.price)


def get_stock(ctx: RunContext[ShopDeps], product: str, size: str | None = None) -> StockInfo | LookupFailure:
    """Look up how many units are in stock, per size, from the inventory table.

    Call this for every availability / "do you have it in M" / "how many left" question.
    Pass `size` when the shopper asks about a specific size; omit it to get every size.

    Args:
        product: The product_id (preferred, from search results) or the product's name.
        size: Optional size: XS, S, M, L, XL, XXL (words like "medium" are accepted).
    """
    ctx.deps.tool_calls.append("get_stock")
    p = resolve_product(ctx, product)
    if isinstance(p, LookupFailure):
        return p

    all_sizes = [SizeAvailability(size=s.size, quantity=s.quantity, status=stock_status(s.quantity)) for s in p.inventory]
    requested = None
    shown = all_sizes
    if size:
        requested = normalize_size(size)
        match = [s for s in all_sizes if s.size == requested]
        if not match:
            return LookupFailure(
                error=f"We don't make the {p.name} in size '{size}'.",
                valid_sizes=[s.size for s in all_sizes],
            )
        shown = match

    ctx.deps.seen_quantities.update(s.quantity for s in all_sizes)
    ctx.deps.seen_quantities.add(sum(s.quantity for s in all_sizes))
    ctx.deps.seen_quantities.add(len([s for s in all_sizes if s.quantity > 0]))
    return StockInfo(
        product_id=p.product_id,
        name=p.name,
        requested_size=requested,
        sizes=shown,
        total_in_stock=sum(s.quantity for s in all_sizes),
        sizes_in_stock=[s.size for s in all_sizes if s.quantity > 0],
        sold_out_sizes=[s.size for s in all_sizes if s.quantity == 0],
    )


# ---------- context tools (who is chatting, what's on screen) ----------

PAGE_TYPES = {"/": "home", "/products": "products", "/about": "about", "/login": "login", "/signup": "signup"}


def get_my_account(ctx: RunContext[ShopDeps]) -> CustomerContext | str:
    """Get the logged-in shopper's own account details (first name, last name, email).

    Use when the shopper asks about their account ("what email am I logged in with?").
    Only ever returns the person currently chatting.
    """
    ctx.deps.tool_calls.append("get_my_account")
    if ctx.deps.customer is None:
        return "The shopper is a guest (not logged in). They can log in or create an account from the top menu."
    return ctx.deps.customer


def get_current_page(ctx: RunContext[ShopDeps]) -> PageInfo | str:
    """Get the page the shopper is looking at right now, including the product on screen.

    Use when the shopper says "this", "it", "this one", or "the one I'm looking at".
    """
    ctx.deps.tool_calls.append("get_current_page")
    page = ctx.deps.page
    if page is None:
        return "No page information was sent with this message."
    product = ctx.deps.current_product
    if product is not None:
        ctx.deps.seen_product_ids.add(product.product_id)
    return PageInfo(
        path=page.path,
        page_type="product_detail" if product else PAGE_TYPES.get(page.path, "other"),
        product=_summary(product, ctx.deps) if product else None,
        showcase_title=page.showcase_title,
    )


# ---------- cart tools ----------

def _cart_quantity(deps: ShopDeps, product_id: str, size: str) -> int:
    return sum(l.quantity for l in deps.cart if l.product_id == product_id and l.size == size)


def _cart_view(deps: ShopDeps) -> CartView:
    ids = list(dict.fromkeys(l.product_id for l in deps.cart))
    products = {p.product_id: p for p in db.products_by_ids(ids)}
    lines: list[CartLineView] = []
    dropped = 0
    for l in deps.cart:
        p = products.get(l.product_id)
        size = normalize_size(l.size)
        if p is None or size is None:
            dropped += 1
            continue
        stock = next((s.quantity for s in p.inventory if s.size == size), 0)
        lines.append(CartLineView(
            product_id=p.product_id, name=p.name, size=size, quantity=l.quantity,
            unit_price=p.price, line_total=round(p.price * l.quantity, 2), in_stock=stock,
        ))
    subtotal = round(sum(l.line_total for l in lines), 2)
    for l in lines:
        deps.seen_prices.update({l.unit_price, l.line_total})
        deps.seen_quantities.update({l.quantity, l.in_stock})
    deps.seen_prices.add(subtotal)
    deps.seen_quantities.add(sum(l.quantity for l in lines))
    return CartView(
        lines=lines,
        item_count=sum(l.quantity for l in lines),
        subtotal=subtotal,
        note=f"{dropped} unknown item(s) were ignored." if dropped else None,
    )


def view_cart(ctx: RunContext[ShopDeps]) -> CartView:
    """See what's in the shopper's cart, priced from the database, with a subtotal.

    Use for "what's in my cart?", "what's my total?", or before suggesting additions.
    """
    ctx.deps.tool_calls.append("view_cart")
    return _cart_view(ctx.deps)


def add_to_cart(
    ctx: RunContext[ShopDeps], product: str, size: str, quantity: int = 1
) -> CartActionResult | LookupFailure:
    """Add a product in a specific size to the shopper's cart (the website updates instantly).

    Only call this when the shopper clearly asks to add something AND you know the size.
    If they didn't say a size, ask them first; never pick one for them.

    Args:
        product: The product_id (preferred) or name. "this" = the product on screen.
        size: XS, S, M, L, XL, or XXL (words like "medium" are accepted).
        quantity: How many to add (1-10).
    """
    ctx.deps.tool_calls.append("add_to_cart")
    p = resolve_product(ctx, product)
    if isinstance(p, LookupFailure):
        return p
    size_n = normalize_size(size)
    stock = next((s.quantity for s in p.inventory if s.size == size_n), None)
    if size_n is None or stock is None:
        return LookupFailure(error=f"We don't make the {p.name} in size '{size}'.",
                             valid_sizes=[s.size for s in p.inventory])
    if not 1 <= quantity <= 10:
        return LookupFailure(error="Quantity must be between 1 and 10 per request.")
    # Idempotent within a turn: if a fact-check retry makes the model call this again,
    # don't add the same item twice.
    for a in ctx.deps.cart_actions:
        if (a.product.product_id, a.size, a.quantity) == (p.product_id, size_n, quantity):
            view = _cart_view(ctx.deps)
            return CartActionResult(
                added=True, product_id=p.product_id, name=p.name, size=size_n, quantity=quantity,
                unit_price=p.price, quantity_in_cart_now=_cart_quantity(ctx.deps, p.product_id, size_n),
                cart_subtotal=view.subtotal,
            )
    in_cart = _cart_quantity(ctx.deps, p.product_id, size_n)
    ctx.deps.seen_quantities.update({stock, in_cart})
    if stock == 0:
        return LookupFailure(
            error=f"The {p.name} is sold out in {size_n}; nothing was added.",
            valid_sizes=[s.size for s in p.inventory if s.quantity > 0],
        )
    if in_cart + quantity > stock:
        return LookupFailure(
            error=(f"Only {stock} of the {p.name} in {size_n} are in stock and the cart already has "
                   f"{in_cart}; nothing was added. The most they can add is {max(stock - in_cart, 0)}."),
        )
    ctx.deps.cart.append(CartLine(product_id=p.product_id, size=size_n, quantity=quantity))
    ctx.deps.cart_actions.append(CartAction(product=p, size=size_n, quantity=quantity))
    view = _cart_view(ctx.deps)
    ctx.deps.seen_prices.update({p.price, round(p.price * quantity, 2)})
    ctx.deps.seen_quantities.add(quantity)
    return CartActionResult(
        added=True, product_id=p.product_id, name=p.name, size=size_n, quantity=quantity,
        unit_price=p.price, quantity_in_cart_now=in_cart + quantity, cart_subtotal=view.subtotal,
    )


SHOP_TOOLS = [
    search_products,
    list_categories,
    get_product_description,
    get_price,
    get_stock,
    get_my_account,
    get_current_page,
    view_cart,
    add_to_cart,
]
