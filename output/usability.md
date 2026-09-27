# Campus Customs: Usability Improvements (Problem 9)

| # | Type | Improvement | Where to see it |
|---|---|---|---|
| 1 | Front end | **Shopping cart** | Product page → pick a size → **Add to cart** · 🛍 **Cart** in the nav |
| 2 | Front end | **Smarter Products page** | **Products** → toolbar above the grid |
| 3 | Agent/backend | **The assistant can add to and read your cart** | Chat: "add this in M to my cart", "what's my total?" |
| 4 | Agent/backend | **Price & stock fact-check** | Chat: "how much is the Boola Boola T Shirt?" → **✓ Prices & stock checked against live inventory** |

## 1. Shopping cart (front end)
**What I added:**
- A working **Add to cart** button on product pages, with a quantity stepper capped at the stock for the chosen size.
- A slide-out cart drawer where you can change quantities and remove items, with a live subtotal.
- A nav badge that shows the item count.
- The cart is saved in `localStorage` and re-priced from the API each time the page loads. Checkout shows "coming soon".

**Why it helps:** before this, the product page had a dead button, so there was no path from browsing to buying. Now shoppers can collect items, and the business can see intent to buy. Because of the stock caps, no one can put more in the cart than exists.

## 2. Smarter Products page (front end)
**What I added:**
- A sticky toolbar with search, **sort** (price ↑/↓, name, most in stock), category chips, a filter for **in stock in a chosen size** (XS–XXL), and a **price cap slider**.
- A match count and a "Clear N filters" button.
- All of this is saved in the URL (e.g. `?cat=Hoodies&size=M&max=70`), so it survives pressing Back from a product page and can be shared as a link.
- An empty-results state with an **Ask the assistant** button that opens the chat with a pre-written question.

**Why it helps:** "Hoodies in my size under $70" now takes one click instead of opening every product page. Filtering on sizes that are actually in stock means shoppers stop landing on sold-out items. I checked that filter against the DB: 19 items, matching SQL exactly.

## 3. The assistant can add to and read your cart (agent/backend)
**What I added:** two new tools.
- `add_to_cart(product, size, quantity)`:
  - checks the product, size and stock against the DB, counting what's already in the cart;
  - refuses sold-out sizes or quantities beyond stock;
  - asks for a size if the shopper didn't give one;
  - understands "this" as the product on the page;
  - won't add the same item twice within one turn.
- `view_cart()`: reads the cart and prices it **from the DB**.

The site sends its cart with each message, and the server returns `cart_actions`, which the widget applies to the real cart, showing "🛍 Added … · View cart".

**Why it helps:** shoppers can buy through conversation ("add it in M"). The server always does the stock checks and pricing, so a tampered cart can't change prices, and the agent can't add stock that doesn't exist.

## 4. Price & stock fact-check (agent/backend)
**What I added:**
- A PydanticAI `output_validator` checks every `$` amount and every stock count in a reply against the numbers the tools returned **this turn**.
  - Totals are allowed when they're a sum of prices that were looked up.
  - Numbers the shopper typed may be repeated back.
- If a number doesn't match, the reply is sent back to the model to fix (`ModelRetry`). If it still fails after the retries, the shopper gets a safe reply with no numbers.
- Replies that pass show a **✓ Prices & stock checked against live inventory** badge.
- **Tested:** `test_improvements.py` planted a wrong "$25" price in the chat history, and the agent answered with the real $32 instead.
- **Speed:** the check that recognises totals divides every amount by their greatest common divisor first, so it takes about 1 ms.

**Why it helps:** a wrong price quoted in chat is a refund or a complaint waiting to happen. This guarantees numbers are correct instead of trusting the prompt, and the badge gives shoppers a reason to trust the assistant.

**Tests:** `backend/test_improvements.py` (15/15). All the earlier suites still pass (tools 20, chat 19, context 14, auth 15).
