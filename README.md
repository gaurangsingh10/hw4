# Campus Customs — HW4

An AI-powered storefront for **Campus Customs** (Yale apparel):

- a **React + Vite + TypeScript** front end,
- a **FastAPI** back end over SQLite,
- a **PydanticAI** shopping assistant.

The assistant searches the catalogue, answers price and stock questions from the database, puts search results on the page as product cards, knows which product you're looking at, adds items to your cart, and remembers logged-in shoppers.

## 1. Place the data pack (not in git)

The database and product images are course data and are **not** in this repo. Unzip the provided `data.zip` so you have:

```
hw4/
└── data/
    ├── campus_customs.db
    └── products/          # images referenced by the catalogue
```

## 2. Configure secrets

```bash
cp .env.example .env
```

Then edit `.env` and set `PORTKEY_API_KEY`. `PORTKEY_BASE_URL` and `CAMPUS_CUSTOMS_MODEL` (default `gpt-5.6-luna`) can stay as they are. `.env` is gitignored.

## 3. Back end (FastAPI, port 8000)

Requires Python 3.10+. From `hw4/`:

```bash
python3.10 -m venv backend/.venv
backend/.venv/bin/pip install -r requirements.txt
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

When the API starts, it adds two chat-history columns to the database. This is idempotent and only adds columns; nothing is dropped.

## 4. Front end (Vite, port 5173)

Requires Node 20+. In a second terminal, from `hw4/`:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies `/api` and `/media` to the back end on port 8000.

**Test login:** `test@campuscustoms.yale.edu` / `password`, or create an account.

## Try it

- 💬 Chat: *"show me hoodies"*. The results panel of product cards appears on the page.
- On a product page: *"do you have this in pink?"*, *"how many are left in XL?"*, *"add this in M to my cart"*
- 🛍 **Cart** in the nav. **Products** page filters: sort, size in stock, and a price cap.

## Layout

```
hw4/
├── AI_prompts.md            # prompts used for each problem
├── requirements.txt         # back-end Python deps
├── .env.example             # placeholders only
├── frontend/                # Vite React TypeScript app
├── backend/
│   ├── main.py              # FastAPI app (uvicorn main:app --reload --port 8000)
│   ├── agent.py             # agent wiring: model, prompt, tools, fact-check, audit
│   ├── tools.py             # tools the agent can call
│   ├── models.py            # Pydantic / PydanticAI types
│   ├── prompts/prompt.md    # system prompt (voice + safety rules)
│   ├── auth.py, db.py, audit.py   # password hashing/sessions, SQLite access, audit trail
│   └── test_*.py            # end-to-end checks
└── output/
    ├── harness.md           # how the system works (data, auth, models, tools, safety, specs)
    ├── design.md, usability.md
    ├── app_check.html       # live-site check (open in a browser)
    ├── app_check_images/    # screenshots linked from app_check.html
    └── audit_trail.json     # append-only agent-loop log
```

## Tests (optional)

With both servers running, from `hw4/`:

```bash
backend/.venv/bin/python backend/test_tools.py --offline   # no model calls
backend/.venv/bin/python backend/test_auth.py
backend/.venv/bin/python backend/test_chat.py              # live model calls
```

See `output/harness.md` §8 for the full list.
