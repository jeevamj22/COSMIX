# COSMIX

COSMIX reads a cosmetic ingredient list and explains what the retrieved records can, and cannot, support.

It does two jobs:

- **Analyze** a product link or a pasted ingredient list. Names are matched to a local library. Documented concerns keep their source. Unknown names stay unknown.
- **Check** the same list against a skin profile saved on this computer: skin type, allergies, and medicines. The same list and the same profile always give the same profile result.

COSMIX does not diagnose skin from a photo, does not promise that a product will work, and does not call a product safe because an ingredient list looks ordinary.

## Run it

1. Install Python 3.12 from [python.org](https://www.python.org/downloads/) if you do not have it. Tick "Add python.exe to PATH".
2. Double-click `run.bat` in this folder.
3. Leave the black window open. The app opens at http://127.0.0.1:8000
4. Close the window to stop COSMIX.

From a terminal, the same steps are:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On macOS or Linux, use `.venv/bin/python` instead of `.venv\Scripts\python`.

Profiles, checks, analyses, preferences, feedback, and photos are stored in `%LOCALAPPDATA%\COSMIX` on Windows, or in `COSMIX_DATA_DIR` when that variable is set. They are not stored in this project folder.

## How to use it

1. On the first screen, paste a product link and choose **Read ingredients**, or choose **Paste ingredients**.
2. If the page cannot be read, use **Paste manually instead**. The link is kept. Edit the list before analysis. A successful extraction status is shown only after a list was actually found.
3. Read the ingredient notes, the documented concerns, the sources, and the limitations. A preference match means you flagged that name. It is not a new scientific finding.
4. Open **Compare** for two or more lists. Shared names are not shared doses, and no product is scored as the winner.
5. Open **Profile check** when you want the list compared with a saved skin profile. A photo can be attached for your own record. The photo is not analysed.

Skin tone is used for pigmentation risk in the profile check. COSMIX does not recommend products for lightening skin.

## Configuration

Copy `.env.example` to `.env` only if you need optional settings. `run.bat` does not load `.env` by itself. Set the variables in the shell, or in the process manager, before you start uvicorn.

| Variable | Required | Purpose |
| --- | --- | --- |
| `COSMIX_DATA_DIR` | No | Folder for the local SQLite file and uploads. |
| `COSMIX_AI_API_KEY` | No | Enables a retrieval-grounded rewrite. Without it, explanations come from the library. |
| `COSMIX_AI_BASE_URL` | No | OpenAI-compatible base URL. Defaults to `https://api.openai.com/v1` when a key is set. |
| `COSMIX_AI_MODEL` | No | Model name. Defaults to `gpt-4o-mini`. |
| `COSMIX_AI_TIMEOUT_SECONDS` | No | Model timeout. Default 25. |
| `COSMIX_ADMIN_TOKEN` | No | Required to read stored feedback. Feedback can still be submitted without it. |
| `COSMIX_CORS_ORIGINS` | No | Comma-separated origins. Leave empty for same-origin use. |
| `COSMIX_RATE_LIMIT_PER_MINUTE` | No | Limit for extract, parse, analysis, and compare. Default 60. |
| `COSMIX_LOG_LEVEL` | No | Default `INFO`. URLs are not logged with query strings. |
| `COSMIX_OPEN_BROWSER` | No | `run.bat` sets this to `1`. |

The model, when configured, receives ingredient ids, library text, and source ids. It does not receive profile notes or photos. A model sentence is kept only when every source id it cites was already retrieved. Concerns are not taken from the model.

## Tests

```bash
.venv\Scripts\python -m pytest
```

Tests use HTML fixtures and mocked page fetches. They do not call live shops or a live model.

## Docker

```bash
docker compose up --build
```

The compose file publishes port 8000 and stores data in a volume. There is no login. Do not expose that port to the public internet as if it were a multi-user service.

## What is in this folder

- `app` is the product. FastAPI serves the page and the API.
- `run.bat` starts it on this computer.
- `sources` keeps the chemical PDF you uploaded. That file is a Royal Society of Chemistry classroom worksheet for teenagers, not a safety database. Some of its lines are wrong, so the checker does not use it as medical advice.
- `legacy` is the earlier "chat with a PDF" experiment. Do not run that for real checks. It can invent an answer.
- `reference_website` is a visual reference. It is not the application.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness only. No configuration is returned. |
| POST | `/api/v1/products/extract` | Read a public product URL. |
| POST | `/api/v1/ingredients/parse` | Split and match a pasted list. |
| POST | `/api/v1/analysis` | Explain a list from retrieved records. |
| POST | `/api/v1/products/compare` | Compare two to four lists. |
| GET | `/api/v1/ingredients/{id}` | One library record and its stored sources. |
| GET | `/api/v1/products/platforms` | Which page readers exist, and that they are best-effort. |
| GET/PUT | `/api/v1/preferences` | Local avoid, prefer, and investigate names. |
| GET/DELETE | `/api/v1/analyses` | Local analysis history. |
| POST | `/api/v1/feedback` | A report about a bad extraction or explanation. |
| GET | `/api/v1/feedback` | Review reports. Requires `X-Cosmix-Admin-Token`. |

The older profile routes remain: `/api/profiles`, `/api/checks`, `/api/extract`, `/api/ingredients`.

## Product pages

Extraction allows public `http` and `https` URLs only. Localhost, private, link-local, and reserved addresses are rejected, including after a redirect. Responses are size-capped and timed out. Page JavaScript is not executed. A login wall, captcha, or bot wall stops the read and asks for the ingredient list.

Amazon, Flipkart, Nykaa, Myntra, and Purplle have extra selectors. Those selectors are hints on top of the generic reader. A site that hides the list, blocks the request, or builds the page only in the browser will not yield ingredients. Do not treat the platform list as a promise that every product page works.

Automatic reading should follow the site's terms. This version does not log in, solve a captcha, or bypass an access control.

## Data and evidence

Ingredient relationships (synonym, function, concern) are answered from the curated library in this process. Neo4j is not required and is not started. SQLite holds profiles, analyses, preferences, and feedback.

Regulatory sentences are attached only for a short list of substances, with the EU cosmetics regulation or an FDA page as the source. Other sentences are marked as the COSMIX library. If a name is not in the library, the app does not invent a function or a citation.

There is no account system. History on this computer is not separated by user. Do not put the app on a shared network and treat those records as private to one person.

## Troubleshooting

- **Python is not recognized.** Reinstall Python and tick "Add python.exe to PATH", then open a new terminal.
- **The page says the site blocked the read.** Paste the ingredient list. That is the supported fallback.
- **The analysis says no AI key is configured.** That is expected. The result still uses the library. Set `COSMIX_AI_API_KEY` only if you want the optional rewrite.
- **Port 8000 is already in use.** Stop the other COSMIX window, or start uvicorn with `--port 8001`.

## Before you put this on the internet

The old `env.example` file contained live secret keys, and that file was pushed to GitHub. Treat those keys as stolen.

1. Revoke the OpenAI key in your OpenAI account.
2. Revoke the Hugging Face token in your Hugging Face account.
3. Deleting the keys from the file is not enough. They remain in the Git history until the keys are revoked.

Do not commit a new key. The profile check does not need one. The optional analysis rewrite reads `COSMIX_AI_API_KEY` from the environment only.

## Limits that are still true

- The library is a curated shopping set, not a complete INCI database and not a medical record.
- Live shop pages often refuse automated reading. Manual paste is part of the product, not a temporary error.
- Barcode scanning, label photos, and OCR are not implemented. The analysis accepts text so those inputs can be added later.
- No vector search and no graph database are used.
- Without an AI key, wording is deterministic and comes from retrieved records. With a key, the provider must be reachable. A failed provider call keeps the library text.
