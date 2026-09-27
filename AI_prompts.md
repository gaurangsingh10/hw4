# AI Prompts Log — HW4 (Campus Customs Website)

A record of the prompts I sent to Claude Code while working on this assignment.

---

## Setup (before Problem 1)

**Prompts:**
1. "We are going to be working in the HW4 folder today, we will be creating a customer website for campus connect as today's assignment. first prove that we are working in folder HW4 by writing a funny joke in there"
2. "unzip data.zip and look at what's inside"

**Follow-up needed:** None.

---

## Problem 1 — Set up the AI prompt log

**Prompts:**
1. "Got it. let's start with problem 1. Please create an AI_prompts.md and record everything i send to you in this log. Put one section for each problem with the following details; 1. The problem number & tile 2. At least one prompt you typed, in your own words as much as possible 3. One follow-up prompt if it was required ( one sentence on what was missing from the first prompt)"

**Follow-up needed:** None.

---

## Problem 2 — Understand the database & start the harness

**Prompts:**
1. "Now problem 2: I need to look at the database data/campus_customs.db and understand the fields. Prioritize helping me understand catalogue, inventory, and users. Then start the file output/harness.md where you should list each table and its fields, and one short line explaining why each of these fields matters for the shot or the chatbot. we will keep growign this harness file in later problems (models, tools, safety, specs)"

**Follow-up needed:** None.

---

## Problem 3 — Scaffold the React + Vite + TypeScript front end (and a starter FastAPI backend)

**Prompts:**
1. "Alright for problem 3 now we need to scaffold a React + Vite + TypeScript front end for campus customs. We will put a nav bar at the top that links to the main page: 1. Home 2. Products 3. About Us 4. Log In 5. Create Account. Pull the compus customs-style wording from this website: https://yalebulldogblue.com/ for home and about us, but write these pages in my voice (don't just copy the original site text). On the products page, show product images from the catalogue (use the image paths in the database) with basic product info (name, price, and short description). Make each product open a single-item page (large image on one side, full product text on the other - description, price, sizes/stock when you have them). Clicking a card on products should take the shopper there. Add a chat interface in the bottom right of the site (a floating chat panel is fine). It does not need to talk to an agent yet - a stub that will call your backend later is enough for this problem. You will need a small API soon to read the database. It is fine to start a simple FastAPI app in backend/main.py just to serve products and images and then we will later grow it into the agent backend in upcoming problem 5"

**Follow-up needed:** None.

---

## Problem 4 — Create-account / log-in flow with secure password storage

**Prompts:**
1. "now problem 4: we will build a normal create-account/login flow. 1. Create Account: first name, last name, email, password and confirm password to ensure its correct. 2. Log In: email & password. Now all new accounts go into the users table. make sure to store passwords securely so hackers (human or AI) cannot access them. The seed database already has a test user so use that while building. Email: test@campuscustoms.yale.edu and password: password. Confirm that we can login as that user, and create & test a brand-new account as well to make sure this flow works properly. Update output/haness.md with how auth works (what you store for a user and how passwords are protected)."

**Follow-up needed:** None.

---

## Problem 5 — Shop chatbot: PydanticAI agent behind FastAPI, wired to the chat widget

**Prompts:**
1. "now problem 5: we will build the shop chatbot as a PydanticAI agent behind FastAPI plugged into your front-end chat widget. Put the API app in the backend/main.py - that is the file you run with Uvicorn. Keep the agent as these four files next to it: 1. backend/prompts/prompt.md - System prompt (we will grow this file later) 2. Backend/agent.py - (agent entry / wiring), 3. backend/tools.py - (tools the agent can call) 4. backend/models.py - (pydantic / pydanticAI structured types) . Now in main.py, expose a chat route so a message from the website returns a reply from the agent (and whatever else you need for products/auth). Use the AI model API key for the agent.  Put campus customs voice and safety basics into prompts/prompt.md (you will expand tools and safety later). Start or update types in models.py for chat replies / product cards as needed. In output/harness.md, note how the front end talks to FastAPI and how the agent is loaded (prompt file + model). make sure the backend runs from the backend/ folder like this : uvicorn main:app --reload --port 8000 - let me know if you need any further clarifications"

**Follow-up needed:** None.

---

## Problem 6 — Database lookup tools for descriptions, prices, and stock

**Prompts:**
1. "For problem 6, give the agent tools that look up real information from campus_customs.db: 1. Product Descriptions 2. Price 3. How many are in stock (by size when the customer asks). The agent must use the database - it should not invent prices or quantities. If a size is out of stock, say so clearly. Also expand prompts/prompt.md so the agent knows to call these tools for price & stock questions. Add or update return types in models.py . Now in output/harness.md, list each tool and explain which model fields we chose for lookup results and why"

**Follow-up needed:** None.

---

## Problem 7 — Chat search results rendered on the page as dynamic product cards

**Prompts:**
1. "now problem 7: we will add another feature to the site. When a customer asks for a item type (example hoodies etc.), the agent should search the catalogue and the website should dynamically display those matching items as product cards (image, name, price and short info). This is an API contract: the agent returns structured product matches and then. the front end renders them on the website. it should look really cool. After the dynamic product cards are loaded by this new feature, we will make sure the same single-item page behaviour still workds: each product card (including the ones the chat just put on the page) - should still open that detial view (large image + full information) when clicked. update prompts/promt.md and output/harness.md so it is clear how search results reach the page. also give me a link so i can check myself on progress"

**Follow-up needed:** None.

---

## Problem 8 — Persistent chat history, customer identity in agent deps, and page context

**Prompts:**
1. "now problem 8: when a shopper is logged in, save their chat history in the database in an appropriate table and reload it when they return. The agent should know who is chatting (name, email) - and put that in the agent deps (or an equivalent clear pattern) and/or tools the agent can call. also pass enough page context that if someone is on a product page and asks \"do you have this in pink?\", the agent knows which item they mean (you can use code into the agent context to achieve this). Guests can still chat, but the history only needs to persist for logged-in users. Document the following in output/harness.md: how user chat history is stored, what customer fields the agent sees, and how page context is passed."

**Follow-up needed:** None.

---

## Problem 9 — Usability improvements (2 front-end, 2 agent/backend)

**Prompts:**
1. "now problem 9: now that the core shop works, improve it. let's implement 2 front-end usability improvements and 2 agent/backend usability improvements. Front-end improvements are things that make the site look better and make it easier to use. Agent / backend improvements are things that make the agent output better, more accurate, or safer. These could be new agent tools or things that make the agent run faster or cheaper. write output/usability.md before or as you build the improvements. For each improvement, mention what you added, and why it helps a campus customs shopper or the business. Make sure all improvements actually show up in the running app as graders will read the write up and look for the features. Choose features basis best judgement of what will add the most value to the website"

**Follow-up needed:** "Where is the holdup - can we resolve it quickly, effectively and move on ?" — the first prompt didn't set a time budget, so I spent too long re-running a flaky wording check in an old test instead of wrapping up.


---

## Problem 10 — Creative design: Masters-inspired, futuristic storefront

**Prompts:**
1. "Now for problem 10, we will add creative design so the site feels like a real campus customs storefront - fonts, color, hierarchy, motion, product presentation, and chat feel. I love to golf so model this after the masters colour theme and style, and the website should feel like a futuristic version of today (think star trek). Write output/design.md : what you changed, and why it should help customers stick around and buy. Keep it concrete and short"
2. "Do it fast"

**Follow-up needed:** "Do it fast" — the first prompt didn't say speed mattered more than polish, so I was about to over-verify.

---

## Problem 11 — Live app check page (output/app_check.html)

**Prompts:**
1. "now problem 11. we will test the live site and need to document it in output/app_check.html (a page you can double click open). I will attach some screenshots but you can take more to include it in this site. Also include short captions for 1. Chat checking the inventory level of an item (honest stock / price from the DB) 2. The dynamic search-result cards appearing after a category question (e.g. hoodies) 3. One of the usability features added in problem 9. make the HTML easy to grade: heading for each check, screenshot, one or two sentences on what the screenshot proves. Put the screenshot imgage files in output/app_check_images/ and then link them from app_check.html with relative paths (for example app_check_images/invetory.png). - tell me where you need me to add screenshots or captions, and where you can do it yourself. Try to do it yourself if possible." (+ 4 screenshots attached: About, Products, Home leaderboard, Home hero)

**Follow-up needed:** None.

---

## Problem 12 — Append-only audit trail, safety rules, and finishing the harness

**Prompts:**
1. "now problem 12: keep an append-only output/audit_trail.json of agent-loop activity (time, tool name, short args / results, stop reason). Do not wipe it between runs. Also add some safety rules to give the agent and put them in prompts/prompt.md . Finish output/harness.md so it is clear how the system works: 1. model fields in models.py and why you chose them 2. tools and abilities 3. Safety rules 4. Specs (loop limits, result caps, models, how to run front + back)"

**Follow-up needed:** None.

---

## Problem 13 — Push to GitHub and submit the URL

**Prompts:**
1. "now problem 13:" (+ screenshot of the Problem 13 instructions: put the code in a public GitHub repo with the expected `hw4/` layout — AI_prompts.md, requirements.txt, .env.example, .gitignore, README.md, frontend/, backend/, output/ — and keep `.env`, `campus_customs.db`, and product images out of git)

**Follow-up needed:** _TBD_
