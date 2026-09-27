"""Campus Customs shopping agent: model + system prompt + tools, wired together.

main.py calls `run_chat()`; everything model-related lives here.
"""

import logging
import math
import os
import re
import time
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelRetry, RunContext, UsageLimits, capture_run_messages
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

import audit
import db
from models import (
    MAX_SHOWCASE_PRODUCTS,
    AgentReply,
    ChatResponse,
    ChatTurn,
    FactCheck,
    Showcase,
    ShowcaseResult,
)
from tools import SHOP_TOOLS, ShopDeps, run_search

BACKEND_DIR = Path(__file__).resolve().parent
PROMPT_PATH = BACKEND_DIR / "prompts" / "prompt.md"
DEFAULT_MODEL = "gpt-5.6-luna"

# Secrets live in hw4/.env (template: hw4/.env.example); backend/.env also works.
load_dotenv(BACKEND_DIR.parent / ".env")
load_dotenv(BACKEND_DIR / ".env")
log = logging.getLogger("campus_customs.agent")

# Hard caps per chat turn so one message can't run away with tokens or tool calls.
USAGE_LIMITS = UsageLimits(
    request_limit=6,
    tool_calls_limit=8,
    input_tokens_limit=60_000,
    output_tokens_limit=4_000,
)


# Shown when the model provider's content filter blocks a message (e.g. jailbreak attempts).
BLOCKED_REPLY = (
    "Sorry, I can't help with that. I'm here to help you find Campus Customs gear. "
    "Want me to look up a hoodie, crewneck, or tee for you?"
)


# Shown if the model keeps quoting numbers the tools didn't return, even after retries.
UNVERIFIED_REPLY = (
    "Sorry, I couldn't double-check those numbers against our inventory just now. "
    "Could you ask again? You can also see live prices and sizes on each product page."
)


# Shown if a single turn hits the per-turn request/tool/token caps.
LIMIT_REPLY = (
    "That one needed more lookups than I can do in a single reply. "
    "Could you narrow it down (a product, size, or category) and ask again?"
)


class AgentUnavailable(RuntimeError):
    """Raised when the agent can't be built (e.g. missing API key)."""


def make_model() -> OpenAIResponsesModel:
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise AgentUnavailable("PORTKEY_API_KEY is missing; add it to .env (see .env.example).")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1"),
        default_headers={
            "x-portkey-api-key": api_key,
            "x-portkey-provider": "openai",
        },
        timeout=60.0,
        max_retries=2,
    )
    model_name = os.getenv("CAMPUS_CUSTOMS_MODEL", DEFAULT_MODEL)
    return OpenAIResponsesModel(model_name, provider=OpenAIProvider(openai_client=client))


@lru_cache(maxsize=1)
def get_agent() -> Agent[ShopDeps, AgentReply]:
    """Build the agent once, on first use, so the API can start without a key."""
    agent = Agent(
        make_model(),
        deps_type=ShopDeps,
        output_type=AgentReply,
        instructions=PROMPT_PATH.read_text(encoding="utf-8"),
        tools=SHOP_TOOLS,
        retries=2,
    )

    # Dynamic instructions: re-evaluated on every run from this turn's deps.
    @agent.instructions
    def customer_context(ctx: RunContext[ShopDeps]) -> str:
        c = ctx.deps.customer
        if c:
            return (
                "## Who you're talking to\n"
                f"Logged-in shopper: {c.first_name} {c.last_name} <{c.email}>. "
                "This is their own account; you may use their name and confirm their email if they ask."
            )
        return "## Who you're talking to\nA guest (not logged in). You don't know their name or email."

    @agent.instructions
    def page_context(ctx: RunContext[ShopDeps]) -> str:
        page, product = ctx.deps.page, ctx.deps.current_product
        if page is None:
            return ""
        lines = ["## Where the shopper is", f"Current page: {page.path}"]
        if product:
            lines.append(
                f"They are viewing the product page for **{product.name}** (product_id: {product.product_id}). "
                "\"This\", \"it\", \"this one\" and similar mean this product unless they name another. "
                "Still call the lookup tools for its price, colors, and stock."
            )
        if page.showcase_title:
            lines.append(f"The results panel \"{page.showcase_title}\" from your last search is on screen.")
        return "\n".join(lines)

    @agent.output_validator
    def fact_check(ctx: RunContext[ShopDeps], output: AgentReply) -> AgentReply:
        return check_facts(ctx.deps, output)

    return agent


# ---------- Fact-check: numbers in the reply must come from this turn's tools ----------

MONEY_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
SIZE_WORD = r"(?:XS|S|M|L|XL|XXL|small|medium|large)"
STOCK_RES = [
    re.compile(r"\b(\d+)\s+(?:left|in stock|available|remaining|units?|pieces?|in the cart)\b", re.I),
    re.compile(r"\bonly\s+\**(\d+)\b", re.I),
    re.compile(rf"\b(\d+)\s+(?:in|of)\s+(?:size\s+)?{SIZE_WORD}\b"),
    re.compile(r"\((\d+)\s+in stock\)", re.I),
]
MAX_CHECK_CENTS = 500_000  # $5,000: above this, don't attempt combination matching


def _cents(x: float) -> int:
    return round(x * 100)


def _is_combination(amount: int, prices: set[int]) -> bool:
    """True if `amount` (cents) is a sum of the given prices with repetition (e.g. 2 x $68 + $32)."""
    if amount > MAX_CHECK_CENTS or not prices:
        return False
    # Work in units of the common divisor (whole-dollar prices -> ~100x fewer steps).
    g = math.gcd(amount, *prices)
    amount, prices = amount // g, {p // g for p in prices}
    reachable = bytearray(amount + 1)
    reachable[0] = 1
    for c in range(1, amount + 1):
        reachable[c] = any(p <= c and reachable[c - p] for p in prices)
    return bool(reachable[amount])


def check_facts(deps: ShopDeps, output: AgentReply) -> AgentReply:
    """Reject replies that state a price or stock count the tools didn't return this turn.

    Allowed $ amounts: prices seen from tools, sums of them (cart totals), numbers the shopper
    typed, and the showcase max_price. Allowed stock counts: quantities seen from tools and
    numbers the shopper typed. On failure, ModelRetry sends the model back to fix it.
    """
    text = output.reply.replace("**", "")
    extra = set(deps.user_numbers)
    if output.showcase and output.showcase.filters.max_price:
        extra.add(output.showcase.filters.max_price)

    price_cents = {_cents(p) for p in deps.seen_prices}
    amounts = [float(m.replace(",", "")) for m in MONEY_RE.findall(text)]
    bad_prices = [
        a for a in amounts
        if _cents(a) not in price_cents and a not in extra and not _is_combination(_cents(a), price_cents)
    ]

    counts = [int(m) for rx in STOCK_RES for m in rx.findall(text)]
    bad_counts = [c for c in counts if c not in deps.seen_quantities and float(c) not in extra]

    if bad_prices or bad_counts:
        deps.fact_check_failures += 1
        problems = [f"${a:,.2f}" for a in bad_prices] + [f"{c} (stock count)" for c in bad_counts]
        log.warning("Fact-check failed (attempt %d): %s", deps.fact_check_failures, problems)
        raise ModelRetry(
            "Fact-check failed: your reply states " + ", ".join(problems) + ", which doesn't match any "
            "price or stock number returned by your tools in this turn. Call get_price / get_stock / "
            "view_cart for the products you mention and use exactly those numbers, or remove the numbers. "
            "Do not call add_to_cart again for items already added."
        )

    if amounts or counts:
        deps.fact_check = FactCheck(
            prices_checked=len(amounts), stock_checked=len(counts), corrected=deps.fact_check_failures > 0
        )
    return output


def to_message_history(turns: list[ChatTurn]) -> list[ModelMessage]:
    history: list[ModelMessage] = []
    for t in turns:
        if t.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=t.content)]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=t.content)]))
    return history


async def run_chat(message: str, history: list[ChatTurn], deps: ShopDeps) -> ChatResponse:
    """Run one chat turn. `deps` (customer + page context) is built by main.py.

    Every turn, successful or not, appends one entry to output/audit_trail.json.
    """
    deps.user_numbers = {float(n) for n in NUMBER_RE.findall(message)}
    history_msgs = to_message_history(history)
    run_id, started, t0 = audit.new_run_id(), audit.now_iso(), time.perf_counter()
    stop_reason, response, usage = "error", None, None
    with capture_run_messages() as captured:
        try:
            result = await get_agent().run(
                message, deps=deps, message_history=history_msgs, usage_limits=USAGE_LIMITS
            )
            usage = result.usage
            response = _to_response(result.output, deps)
            stop_reason = "completed_after_fact_check_retry" if deps.fact_check_failures else "completed"
        except ModelHTTPError as e:
            if "content_filter" not in str(e.body):
                stop_reason = f"model_http_error_{e.status_code}"
                raise
            stop_reason, response = "content_filter", ChatResponse(reply=BLOCKED_REPLY)
        except UsageLimitExceeded as e:
            log.warning("Usage limit hit: %s", e)
            stop_reason, response = "usage_limit", ChatResponse(reply=LIMIT_REPLY, cart_actions=deps.cart_actions)
        except UnexpectedModelBehavior:
            if not deps.fact_check_failures:
                stop_reason = "unexpected_model_behavior"
                raise
            log.error("Fact-check still failing after retries; returning safe reply")
            stop_reason = "fact_check_failed"
            response = ChatResponse(reply=UNVERIFIED_REPLY, cart_actions=deps.cart_actions)
        except AgentUnavailable:
            stop_reason = "agent_unavailable"
            raise
        finally:
            _audit(run_id, started, t0, message, deps, captured[len(history_msgs):], stop_reason, usage, response)
    return response


def _to_response(output: AgentReply, deps: ShopDeps) -> ChatResponse:
    showcase = build_showcase(output.showcase, deps)
    # Cards are rebuilt from the database, so prices/stock shown to the shopper
    # always come from the source of truth, never from model text. Unknown ids are dropped.
    # When results go on the page, the chat doesn't repeat them as mini-cards.
    products = [] if showcase else db.products_by_ids(output.product_ids)
    return ChatResponse(
        reply=output.reply,
        products=products,
        showcase=showcase,
        cart_actions=deps.cart_actions,
        fact_check=deps.fact_check,
    )


def _audit(run_id, started, t0, message, deps, new_messages, stop_reason, usage, response) -> None:
    try:
        audit.append({
            "run_id": run_id,
            "started_at": started,
            "finished_at": audit.now_iso(),
            "duration_ms": round((time.perf_counter() - t0) * 1000),
            "model": os.getenv("CAMPUS_CUSTOMS_MODEL", DEFAULT_MODEL),
            "shopper": "logged_in" if deps.customer else "guest",  # no names/emails in the log
            "page": deps.page.path if deps.page else None,
            "message": audit.short(message, 120),
            "steps": audit.steps_from_messages(new_messages),
            "tools_called": deps.tool_calls,
            "fact_check_retries": deps.fact_check_failures,
            "usage": {"requests": usage.requests, "input_tokens": usage.input_tokens,
                      "output_tokens": usage.output_tokens} if usage else None,
            "result": {
                "reply": audit.short(response.reply, 160),
                "cards": len(response.products),
                "showcase": response.showcase.title if response.showcase else None,
                "cart_actions": len(response.cart_actions),
                "fact_check": response.fact_check.model_dump() if response.fact_check else None,
            } if response else None,
            "stop_reason": stop_reason,
        })
    except Exception:  # the audit log must never break a shopper's chat
        log.exception("Failed to write audit entry")


def build_showcase(showcase: Showcase | None, deps: ShopDeps) -> ShowcaseResult | None:
    """Turn the agent's showcase request into real cards by re-running the search server-side.

    The agent only chooses *what* to search for; the product list itself always comes
    from run_search() over the database, so it can't contain made-up items.
    """
    if showcase is None:
        return None
    filters = showcase.filters
    if filters.is_empty() and deps.last_search is not None:
        filters = deps.last_search  # agent forgot the filters: use its last actual search
    if filters.is_empty():
        return None  # never dump the whole catalogue
    total, matches = run_search(filters)
    if total == 0:
        return None
    return ShowcaseResult(
        title=showcase.title,
        filters=filters,
        total_matches=total,
        products=matches[:MAX_SHOWCASE_PRODUCTS],
    )
