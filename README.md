# Flooring Hotspot GPT

A ChatGPT GPT bot that finds **hot topics on competitor flooring websites
via Semrush** and turns them into Blog / LinkedIn / cold-email selections
for B2B exporters of SPC, PVC, LVT, vinyl, and commercial flooring.

Supports **BYOK (Bring Your Own Key)** — users register their own
Semrush API key on a small `/setup` page, get a short access code
(`floor-XXXX-XXXX`), and the GPT calls Semrush on their behalf with
their own key. Per-user daily/monthly quotas built in.

```
ChatGPT GPT  ─(Actions, Bearer auth, sends user_token)─►  FastAPI middleware
                                                              │
                          /setup HTML page  ─►  /register ─►  SQLite  (encrypted Semrush key per user)
                                                              │
                                                              ▼
                                                  pick adapter:
                                                    byok  → user's key
                                                    real  → server key
                                                    mock  → fake data
                                                    csv   → uploaded CSV
                                                              │
                                                              ▼
                                          Normalize → Cluster → Score → Export
```

## What this project actually delivers

| Layer | Files |
|---|---|
| GPT system prompt | `gpt/system_prompt.md` |
| GPT conversation starters | `gpt/conversation_starters.md` |
| GPT Actions OpenAPI 3.1 schema | `gpt/actions_openapi.yaml` |
| ChatGPT setup walkthrough | `gpt/chatgpt_setup_guide.md` |
| FastAPI middleware | `app/` |
| Semrush real adapter (per-user key supported) | `app/adapters/semrush_real.py` |
| Semrush mock adapter (deterministic) | `app/adapters/semrush_mock.py` |
| Manual CSV adapter | `app/adapters/csv_import.py` |
| **BYOK 衣帽间** — encrypted SQLite store | `app/storage.py`, `app/crypto.py` |
| **BYOK** API endpoints (`/register`, `/revoke`, `/usage`) | `app/routers/byok.py` |
| **BYOK** setup page (HTML form) | `app/static/setup.html` (served at `/setup`) |
| Per-user daily/monthly quota check | `app/services/quota.py` |
| Flooring taxonomy (rule-based) | `app/data/flooring_taxonomy.py` |
| Topic clustering | `app/services/clustering.py` |
| Hotness / Buyer / Product Fit / Opportunity scoring | `app/services/scoring.py` |
| CSV / XLSX / JSON export | `app/services/exporter.py` |
| Tests | `tests/` |
| Sample CSV | `samples/sample_competitors.csv` |

---

## Quick start (mock mode — no Semrush key needed)

```bash
# 1. Clone and set up the venv
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Copy and edit env
cp .env.example .env
# DATA_SOURCE_MODE=mock is fine for first-run

# 3. Run
uvicorn app.main:app --reload --port 8000

# 4. Smoke test
curl -s http://127.0.0.1:8000/health | jq
curl -s -X POST http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"competitor_domains":["shaw.com","mohawkflooring.com"],"product_focus":"commercial","output_use_case":"linkedin"}' | jq '.topics[0:3]'
```

You should see a `data_source: "mock"` payload with topics like
`Commercial Flooring Solutions`, `LVT vs SPC`, `Wholesale Flooring`,
each with explainable scores.

## BYOK mode (recommended for sharing the GPT)

In BYOK mode, every user brings their own Semrush API key. Your server
never spends Semrush units on their behalf — and you can give one GPT
link to many users without going broke.

**1. Generate a Fernet key** (one-time, keep it safe):
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**2. Set `.env`:**
```bash
DATA_SOURCE_MODE=byok
KEY_ENCRYPTION_SECRET=<the Fernet key from step 1>
DATABASE_PATH=./byok.db
DEFAULT_DAILY_QUOTA=50
DEFAULT_MONTHLY_QUOTA=800
VALIDATE_SEMRUSH_ON_REGISTER=true
PUBLIC_BASE_URL=https://your-public-host.example.com
```

**3. Start the server**, then point users at `https://your-host/setup`.
On that page they paste their Semrush key + a nickname → server validates
the key with one cheap real call → returns a `floor-XXXX-XXXX` access
code they paste into the GPT chat ("我的访问码是 floor-7K3Q-9WX2,
分析 shaw.com").

**Lookup flow per request:**

1. GPT sends `analyzeHotTopics` with `user_token`
2. Middleware looks up the row, decrypts that user's Semrush key
3. Quota check (per token, daily + monthly)
4. SemrushReal adapter is instantiated with **that user's key**
5. Usage counters bumped, `quota_used_today` returned to GPT

**BYOK API** (you don't need to call these yourself — the `/setup` page does):

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/register` | Body: `{semrush_api_key, label, daily_quota?, monthly_quota?}` → returns `{user_token, ...}` |
| `POST` | `/revoke` | Body: `{user_token}` → marks token revoked |
| `GET`  | `/usage/{user_token}` | Stats: status, day/month counts, limits, last_used_at |
| `GET`  | `/setup` | The HTML form users fill in |

## Switching to shared Semrush key (single-team mode)

If you'd rather pay for everyone yourself:

```bash
# .env
DATA_SOURCE_MODE=real
SEMRUSH_API_KEY=sm_live_xxx
```

Same `/analyze` call now uses your one server-side key. The
`user_token` field becomes optional/ignored. If the real adapter init
fails (bad key, network), the server falls back to mock for that call
and `data_source: "mock"` lets the GPT warn the user.

## Switching to manual CSV mode

When Semrush is unavailable but you have a CSV export from the Semrush
UI (or a manually compiled list), POST it to `/import-csv`:

```bash
curl -s -X POST http://127.0.0.1:8000/import-csv \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -F 'file=@samples/sample_competitors.csv' \
  -F 'product_focus=commercial' \
  -F 'output_use_case=cold_email' | jq '.topics[0:3]'
```

CSV column names are case-insensitive and aliasing is supported (see
`app/adapters/csv_import.py`).

## Wiring it up to ChatGPT

See `gpt/chatgpt_setup_guide.md` for the click-by-click walkthrough.
The 4 files you'll touch in the GPT editor are:

1. **Instructions** ← `gpt/system_prompt.md`
2. **Conversation starters** ← `gpt/conversation_starters.md`
3. **Actions → Schema** ← `gpt/actions_openapi.yaml` (after editing the `servers.url` to your HTTPS URL)
4. **Actions → Authentication** ← Bearer + your `API_BEARER_TOKEN`

The middleware MUST be reachable at an HTTPS URL — for local dev,
`cloudflared tunnel --url http://localhost:8000` is the fastest way.

## API surface

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/health` | Liveness, also reports current data-source mode |
| `POST` | `/analyze` | Main GPT entry point (Semrush or mock) |
| `POST` | `/import-csv` | Same pipeline, but reads from an uploaded CSV |
| `POST` | `/export` | Write a topic list to CSV/XLSX/JSON, return URL |
| `GET`  | `/exports/{filename}` | Download the generated file |
| `GET`  | `/docs` | Auto-generated OpenAPI / Swagger UI |
| `GET`  | `/openapi.json` | Machine-readable schema (alternative to the YAML in `gpt/`) |

## Scoring model (one-paragraph version)

Each canonical topic gets four 0-100 scores. **Hotness** combines how
many distinct competitors cover the topic, total page traffic, total
keyword search volume, and what fraction of rows fell inside the
freshness window. **Buyer relevance** starts from a taxonomy-defined
baseline (e.g. "Wholesale Flooring" = 1.0, "Maintenance & Cleaning" =
0.4) and adds a bonus for procurement-language hits in titles/keywords
("wholesale", "distributor", "MOQ", "lead time", ...). **Product fit**
weights the taxonomy product signal plus how many SPC/PVC/LVT/Vinyl/
Commercial markers appear, with a bonus/penalty when the user pinned a
specific `product_focus`. **Opportunity** is a weighted blend whose
weights shift by `output_use_case` — cold email puts ~55% weight on
buyer relevance, blog puts ~45% on hotness. Every score returns with a
machine-readable `score_explanation` so the GPT (and the human reading)
can always see why.

## Tests

```bash
pytest -q
```

Covers clustering matches, fallback bucket behavior, score bounds,
explainability, cold-email weighting, and product-focus penalty.

## Project layout

```
flooring-hot-topics-gpt/
├── README.md
├── requirements.txt
├── .env.example
├── gpt/
│   ├── system_prompt.md
│   ├── conversation_starters.md
│   ├── actions_openapi.yaml
│   └── chatgpt_setup_guide.md
├── app/
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── routers/   {analyze, importer, export, health, security}
│   ├── adapters/  {base, semrush_real, semrush_mock, csv_import}
│   ├── services/  {normalizer, clustering, scoring, exporter}
│   └── data/flooring_taxonomy.py
├── samples/sample_competitors.csv
└── tests/  {test_clustering, test_scoring}
```

## Roadmap (left out of MVP on purpose)

- Persist competitor lists per user (currently fully stateless)
- Cache Semrush responses (units cost money — add Redis when usage warrants it)
- Real freshness windows via Semrush historical reports (requires Historical Data subscription)
- Switch the rule-based clusterer to a hybrid embedding model once the
  taxonomy plateaus
