# Cost & limitations report

## Cost

| Item | Cost | Notes |
|---|---|---|
| Data sources | £0 | All integrated sources are free and openly licensed (OGL v3.0, CC BY 4.0, ECB reuse terms). |
| API keys | £0 | None required. Optional free keys: Companies House (register), NOMIS uid. |
| AI / LLM | £0 | Not used. Findings, statistics and scenarios are deterministic code. |
| Software | £0 | Open-source stack (FastAPI, PostgreSQL, Next.js, ECharts, MapLibre, pandas, statsmodels). |
| Basemap tiles | £0 | None by default (boundaries rendered on a plain background). An optional free style URL can be configured. |
| Hosting | £0 locally | Docker Compose on your own machine. Free cloud tiers may work but are not guaranteed (see deployment guide). |
| Fonts | £0 | Geist via Google Fonts at build time. |

`GET /api/meta` returns `"paid_dependencies": []`.

## Load placed on sources (default schedule)

| Source | Requests per scheduled run | Runs/day | Limit respected |
|---|---|---|---|
| ONS | 59 (one JSON per series) | 4 | documented 120/10 s & 200/min; client uses ≤ 80% |
| BoE | 2 | 4 | none published; 1 req / 2 s |
| ECB | 1 | 4 | none published; 1 req / s |
| NOMIS | 13 | 1 | 25,000-cell guest limit; every request is sized below it |
| Land Registry | 1 SPARQL query | 1 | none published; 1 query / s |
| HMRC | 4 | 1 | documented 60/min (client uses ≤ 48/min) |
| NESO | 2 | 48 | none published; 1 req / s |
| DESNZ fuel | 2 | 2 | 1 req / s |
| DMO | 1 | 1 | 1 req / 5 s (currently blocked, see below) |
| ONS Geography | 3 | monthly | 1 req / s |

Retries use exponential backoff with jitter (max 4 attempts) and honour `Retry-After` on 429/5xx. ETag /
Last-Modified conditional requests are used where servers support them.

## Known limitations

**Data coverage**
- **UK DMO gilts in issue is usually unavailable.** On 2026-10-26 the DMO site redirected requests with this
  platform's honest User-Agent to a bot-protection challenge. The platform does not spoof browsers or bypass
  bot protection. Debt totals come from ONS public sector finances instead; the gilt tile shows labelled demo
  data only in fallback mode.
- **No equity indices.** FTSE data is proprietary; no free source with verified redistribution terms was found.
- **BoE spot FX disabled by default** (possible LSEG/Bloomberg content; redistribution restricted). Sterling
  crosses are derived from ECB reference rates.
- **ONS PPI not shown**: the checked series (e.g. GB7S) had no observations after Jan 2025 at verification time.
- **DESNZ Energy Trends / quarterly energy prices not parsed** (spreadsheets with changing layouts).
- **Regional GVA and regional trade (HMRC RTS) are not yet integrated.** HMRC's OData API exposes an `RTS`
  entity that could be added.
- **Local-authority boundaries vs data vintages**: maps use 2025 LAD boundaries; NOMIS returns 2023-vintage LA
  codes. Areas whose codes changed show "No data" rather than a guessed match.
- **Land Registry UK HPI** is integrated at UK/nation/ITL1 level only (local-authority HPI exists but is not yet
  mapped to GSS codes). Price Paid queries work by district name.
- **HMRC OTS** covers goods only, NSA, current prices, and is revised; it is not comparable to ONS BoP trade.

**Timeliness**
- Nothing is real-time except NESO's half-hourly estimates. BoE data are end-of-day (published T+1); ECB
  reference rates are daily; official statistics follow release calendars. Every view labels its timing class.
- Scheduled polling means new releases appear up to one poll interval after publication (6 h for ONS/BoE/ECB,
  24 h for NOMIS/Land Registry/HMRC).

**Statistical**
- Correlations are associations on short, autocorrelated samples; p-values are naïve. The UI states this.
- Outlier flags use a robust but simple rule; they are prompts, not verdicts.
- Uncertainty is shown only where the source publishes it.
- Revision detection starts from the first ingestion; earlier revisions are only visible through ONS vintages.

**Operational**
- One worker process must run (two would double-poll). No authentication for read endpoints — put a reverse
  proxy with auth in front if the data or saved views should be private.
- Free hosting tiers may sleep; data will then be shown as stale. No uptime guarantee is made.
- Endpoints, schemas and licences can change. Run `python -m app.cli verify --write` regularly; schema
  validation failures are surfaced as `validation` alerts and never ingested.
