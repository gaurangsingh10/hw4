"""Pydantic / PydanticAI structured types for the Campus Customs API and agent."""

from typing import Literal

from pydantic import BaseModel, Field

MAX_MESSAGE_CHARS = 1000
MAX_CARDS_PER_REPLY = 6


# ---------- Catalogue ----------

class SizeStock(BaseModel):
    size: str
    quantity: int


class ProductCard(BaseModel):
    """Everything the website needs to render a product card or detail page."""

    product_id: str
    name: str
    garment_type: str
    category: str
    description: str
    colors: list[str]
    search_tags: list[str]
    image_url: str
    price: float
    inventory: list[SizeStock]
    total_stock: int


class ProductSummary(BaseModel):
    """Compact product view returned by the search tool, to keep model context small."""

    product_id: str
    name: str
    category: str
    price: float
    colors: list[str]
    sizes_in_stock: list[str]


class SearchResults(BaseModel):
    total_matches: int = Field(description="How many products matched in total (may exceed the ones shown).")
    showing: list[ProductSummary]


# ---------- Lookup tool results (Problem 6) ----------
# Each lookup returns only the fields needed to answer that one kind of question,
# always with product_id + name so the agent can cite the item and fill product_ids.

StockStatus = Literal["in_stock", "low_stock", "sold_out"]
LOW_STOCK_THRESHOLD = 3


def stock_status(quantity: int) -> StockStatus:
    if quantity <= 0:
        return "sold_out"
    return "low_stock" if quantity <= LOW_STOCK_THRESHOLD else "in_stock"


class ProductDescription(BaseModel):
    """Result of get_product_description: what the item is and looks like."""

    product_id: str
    name: str
    category: str
    garment_type: str
    description: str
    colors: list[str]


class PriceInfo(BaseModel):
    """Result of get_price: the price straight from the catalogue table."""

    product_id: str
    name: str
    price: float = Field(description="Price in USD from the database. Quote exactly, e.g. $68.00.")
    currency: Literal["USD"] = "USD"


class SizeAvailability(BaseModel):
    size: str
    quantity: int = Field(description="Units on hand from the inventory table.")
    status: StockStatus = Field(description="sold_out = 0, low_stock = 1-3, in_stock = 4+.")


class StockInfo(BaseModel):
    """Result of get_stock: per-size inventory for one product."""

    product_id: str
    name: str
    requested_size: str | None = Field(
        default=None, description="The size the shopper asked about, if any (normalized, e.g. 'M')."
    )
    sizes: list[SizeAvailability] = Field(
        description="Only the requested size when one was asked for, otherwise every size XS-XXL."
    )
    total_in_stock: int = Field(description="Units on hand across all sizes.")
    sizes_in_stock: list[str]
    sold_out_sizes: list[str]


class LookupFailure(BaseModel):
    """Returned instead of a result when the product or size can't be resolved."""

    error: str
    did_you_mean: list[ProductSummary] = Field(
        default_factory=list, description="Closest catalogue matches; ask the shopper which one they meant."
    )
    valid_sizes: list[str] = Field(default_factory=list)


# ---------- Showcase: chat search results rendered on the page (Problem 7) ----------

MAX_SHOWCASE_PRODUCTS = 60
Category = Literal["T-Shirts", "Crewnecks", "Hoodies", "Quarter-Zips", "Jackets & Fleece"]


class SearchFilters(BaseModel):
    """The same filters search_products accepts. The server re-runs them to fill the page."""

    query: str | None = Field(default=None, description="Free-text keywords, e.g. 'saybrook', 'hockey'.")
    category: Category | None = None
    color: str | None = None
    max_price: float | None = None
    size: str | None = Field(default=None, description="Only products with this size in stock.")

    def is_empty(self) -> bool:
        return not any([self.query, self.category, self.color, self.max_price, self.size])


class Showcase(BaseModel):
    """Agent -> server: 'put these search results on the page'."""

    title: str = Field(
        max_length=60,
        description="Short heading for the results panel, e.g. 'Navy hoodies under $70' or 'Saybrook College gear'.",
    )
    filters: SearchFilters = Field(
        description="Exactly the filters of the search_products call whose results you're presenting."
    )


class ShowcaseResult(BaseModel):
    """Server -> website: the fully hydrated results panel."""

    title: str
    filters: SearchFilters
    total_matches: int
    products: list[ProductCard] = Field(description=f"Up to {MAX_SHOWCASE_PRODUCTS} matches, best first.")


# ---------- Agent output ----------

class AgentReply(BaseModel):
    """Structured output the agent must return on every turn."""

    reply: str = Field(
        description="Message to the shopper in Campus Customs voice. Markdown allowed (bold, bullet lists)."
    )
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_CARDS_PER_REPLY,
        description=(
            "product_id values (exactly as returned by tools) of the specific products discussed in the reply "
            "(e.g. the item whose price or stock you looked up). Shown as small cards inside the chat. "
            "Leave empty when you set `showcase`, and for general chat."
        ),
    )
    showcase: Showcase | None = Field(
        default=None,
        description=(
            "Set when the shopper is browsing a type, category, color, collection, or price range "
            "(e.g. 'show me hoodies'). The website displays every match as product cards on the page. "
            "None for single-product questions and general chat."
        ),
    )


# ---------- Who is chatting & where they are (Problem 8) ----------

class CustomerContext(BaseModel):
    """The logged-in shopper, as the agent sees them. Built server-side from the session cookie."""

    first_name: str
    last_name: str
    email: str


class PageContext(BaseModel):
    """What the shopper is looking at, sent by the website with every chat message."""

    path: str = Field(max_length=200, description="Current route, e.g. '/products/basic-hoodie-big-yale'.")
    product_id: str | None = Field(default=None, max_length=120, description="Set on a product detail page.")
    showcase_title: str | None = Field(default=None, max_length=60, description="Results panel on screen, if any.")


class PageInfo(BaseModel):
    """Result of the get_current_page tool: the page context, verified against the database."""

    path: str
    page_type: Literal["home", "products", "product_detail", "about", "login", "signup", "other"]
    product: ProductSummary | None = Field(
        default=None, description="The product on screen. 'this', 'it', 'this one' refer to it."
    )
    showcase_title: str | None = None


# ---------- Cart (Problem 9) ----------
# The cart lives in the browser (localStorage) and is sent with each chat message.
# The server re-prices it from the DB, so a tampered cart can't change prices.

MAX_CART_LINES = 50


class CartLine(BaseModel):
    """One line of the shopper's cart as sent by the website."""

    product_id: str = Field(max_length=120)
    size: str = Field(max_length=10)
    quantity: int = Field(ge=1, le=99)


class CartLineView(BaseModel):
    product_id: str
    name: str
    size: str
    quantity: int
    unit_price: float
    line_total: float
    in_stock: int = Field(description="Units currently in stock for this size.")


class CartView(BaseModel):
    """Result of view_cart: the cart priced from the database."""

    lines: list[CartLineView]
    item_count: int
    subtotal: float
    note: str | None = None


class CartAction(BaseModel):
    """Server -> website: an item the assistant added; the site applies it to the cart."""

    type: Literal["add"] = "add"
    product: ProductCard
    size: str
    quantity: int


class CartActionResult(BaseModel):
    """Result of add_to_cart."""

    added: bool
    product_id: str
    name: str
    size: str
    quantity: int
    unit_price: float
    quantity_in_cart_now: int
    cart_subtotal: float


# ---------- Fact-check (Problem 9) ----------

class FactCheck(BaseModel):
    """Reported with replies that quote prices or stock, after they pass validation."""

    prices_checked: int
    stock_checked: int
    corrected: bool = Field(description="True if a wrong number was caught and the model fixed it.")


# ---------- Chat API ----------

class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    # Only used for guests; logged-in history is loaded from chat_messages instead.
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    page: PageContext | None = None
    cart: list[CartLine] = Field(default_factory=list, max_length=MAX_CART_LINES)


class ChatResponse(BaseModel):
    reply: str
    products: list[ProductCard] = Field(default_factory=list)
    showcase: ShowcaseResult | None = None
    cart_actions: list[CartAction] = Field(default_factory=list)
    fact_check: FactCheck | None = None


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    products: list[ProductCard] = Field(default_factory=list)
    showcase: ShowcaseResult | None = None  # re-run from saved filters, so cards are current
    created_at: str
