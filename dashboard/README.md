# Glue — Painel operável (local dashboard)

A zero-dependency, **stdlib-only** web dashboard that lets a human *operate* the
Glue foundation — create companies, seed a chart of accounts, post balanced
journal entries, read a trial balance — instead of only reading the static
catalog in [`docs/`](../docs).

It is a thin bridge, not a second backend: every click routes through the exact
same entry point the AI assistant uses —
`python3 scripts/db_query.py --action <name> [--flags]`. The browser can't shell
out, so a small `http.server` does it, validates the action against the bundled
allowlist (`bin/erpclaw list`), and returns the JSON.

## Run

```bash
python3 dashboard/server.py            # http://127.0.0.1:8787
python3 dashboard/server.py --port 9000
ERPCLAW_DASH_PORT=9000 python3 dashboard/server.py
```

No `pip install`. Same Python (3.11+) that runs the foundation. Binds to
**localhost only** — it writes to your real books at
`~/.openclaw/erpclaw/data.sqlite`.

First time? Open the **Painel** tab → *Inicializar DB* → *Criar empresa* →
*Semear plano de contas*. Then go to **Lançamento** and post one.

## What it does

| View | Actions it drives |
|------|-------------------|
| **Painel** | `get-schema-version`, `list-companies`, `initialize-database`, `setup-company`, `seed-defaults`, `setup-chart-of-accounts` |
| **Plano de contas** | `list-accounts`, `get-account-balance` |
| **Lançamento** | `add-journal-entry` → `submit-journal-entry --user-confirmed` (auto-attaches the company default cost center to P&L lines; live debit/credit balance check) |
| **Relatórios** | `trial-balance`, `profit-and-loss`, `balance-sheet` — all rendered as tables; the balance sheet carries an A = L + E reconciliation badge |
| **Console** | any of the ~463 core actions, as `--key value` pairs, with an optional `--user-confirmed` toggle |

## Design notes

- **`server.py`** — `ThreadingHTTPServer`. `GET /` serves the SPA; `GET
  /api/actions` returns the allowlist; `POST /api/action {action,args,confirm}`
  execs the router with `subprocess` (a list argv — never `shell=True`),
  parses the first JSON value out of stdout, and returns
  `{ok, parsed, stdout, stderr, returncode}`.
- **`index.html`** — single-file vanilla SPA (no build step, no CDN), themed to
  match the `docs/` panels.
- **Safety** — action names are regex- and allowlist-checked; arg *values* are
  passed as separate argv items so they can't inject flags or shell syntax;
  high-impact actions require the explicit confirm toggle, mirroring the
  foundation's own `--user-confirmed` guard.

## Scope

This is a local operator console for the **core foundation** (the 15 bundled
domains). It is not the hosted product UI; the full dashboards
([erpclaw-web](https://github.com/avansaber/erpclaw-web),
[webclaw](https://github.com/avansaber/webclaw)) live in their own repos.
The trial balance, P&L, and balance sheet render as tables; other statements
(e.g. `cash-flow`) are reachable via the **Console** and return JSON.
