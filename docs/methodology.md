# Methodology & statistical rules

Everything here is deterministic and implemented in `backend/app/analytics/` (no AI model is involved).

## 1. Measure types decide what is allowed

Each series has a `measure_type` in the catalogue. The API applies these rules and returns the reason when a
transformation is refused (`/api/series/{id}` → `rules`):

| Measure type | Examples | Changes expressed as | % change | Rebase to 100 |
|---|---|---|---|---|
| level | £m, jobs, enterprises | % | yes | yes |
| index | output indices, CPI index | % (points shown as caveat) | yes | yes |
| price | £, p/litre, FX rates | % | yes | yes |
| rate | unemployment, Bank Rate, gilt yields | **percentage points** | refused | refused |
| growth_rate | CPI 12-month rate, GDP q/q | **pp** (acceleration, caveated) | refused | refused |
| share | debt % GDP, generation shares | **pp** | refused | refused |

Further rules:
- **Year-on-year** is matched by calendar (same month/quarter one year earlier), never by row position, so
  gaps cannot shift comparisons. Daily data compare with the nearest earlier observation 365 days back (within
  7 days, otherwise blank). For a series that is already a growth rate, "year-on-year" is the pp difference and
  is labelled as acceleration.
- **Period-on-period** on not-seasonally-adjusted monthly/quarterly/weekly data carries a seasonal caveat;
  rolling-window survey estimates (APS) carry an overlap caveat.
- **Seasonal decomposition** (STL, robust) is offered only for NSA monthly/quarterly series with ≥3 years of
  data, and labelled as descriptive (not the publisher's official adjustment). It is refused for SA series to
  avoid double adjustment.
- **Rolling means** are trailing, with a minimum of ⌊w/2⌋+1 observations.

## 2. Statistical context

- **Outliers**: robust z = 0.6745·(x − median)/MAD on period-on-period changes; |z| ≥ 3.5 is flagged. A flag is
  a prompt to check the release, not a claim of error. Ingestion raises `outlier` alerts for the latest three
  periods.
- **Volatility**: standard deviation of period-on-period changes, all history and most recent 24.
- **Historical position**: min/max with dates, 10-year mean, 10-year percentile, last time a higher/lower value
  occurred.
- **Missing data**: null values, suppressed values (source flags), and gaps in the expected monthly/quarterly/
  annual sequence. Daily/weekly/half-hourly gaps (non-publication days) are not enumerated.
- **Uncertainty**: shown **only** where the source publishes it — APS 95% confidence intervals and ASHE
  coefficients of variation (CV > 20% flagged unreliable). Otherwise the workspace states that the endpoint
  publishes no uncertainty measure.

## 3. Relationships (association, never causation)

- Series are aggregated to the coarser common frequency (mean within period).
- Default basis is **period-on-period changes** (levels of trending series correlate spuriously; the levels
  option carries an explicit warning).
- Reported: Pearson r with Fisher-z 95% interval, Spearman ρ, n, naïve p-value (flagged as overstated when
  series are autocorrelated), and cross-correlation for lags −12…+12. Lag *k* > 0 means the second series is
  shifted *k* periods earlier. Every response carries the warning that correlation is not causation and that
  scanning many lags inflates the chance of a spurious peak.
- Real and demo data are never correlated together (HTTP 409).

## 4. Findings

Typed and evidence-backed:
- **fact** — read from or arithmetic on displayed values (latest value, change vs previous, year change,
  highest-since);
- **interpretation** — contextual comparison (percentile in 10-year range, recent outlier flags);
- **hypothesis** — only from associations with |r| ≥ 0.5, always worded as unproven.

## 5. Scenarios

Mechanical what-if projections, never forecasts: *unchanged*, *recent average change* (mean of the last 12
period-on-period changes) or *custom step*. The formula is returned and displayed. For pp-type measures the
step is additive in pp; otherwise multiplicative in %.

## 6. Data status

Per series (relative to the source's own schedule):

| Status | Rule |
|---|---|
| current | Retrieved within the source's `stale_after_hours` and consistent with the publication calendar |
| provisional | Latest observation flagged provisional (NOMIS flags; UK HPI latest two months by documented practice) |
| delayed | Publisher's announced next release (ONS `nextRelease`) passed +1 day without a newer release; or, only when no calendar is published, latest period older than a frequency heuristic (stated as heuristic) |
| stale | No successful retrieval within `stale_after_hours` — our copy may be out of date |
| unavailable | No real observation ever retrieved |
| demo | No real observation; labelled synthetic sample shown (demo mode fallback/only) |

## 7. Revisions

1. **Detected revisions**: every ingestion compares incoming values with stored ones; changes are written to
   `observation_revisions` (old/new value, release dates, run) and raise a `revision` alert.
2. **Published vintages** (ONS): the series JSON exposes `versions[]`; `/api/series/{id}/vintages` fetches earlier
   versions on demand (cached; immutable) and tabulates them against current values.

## 8. Derived series

GBP/USD, GBP/EUR and GBP/JPY are computed from ECB reference rates (`1/GBPperEUR`, `USDperEUR/GBPperEUR`, …)
only on dates where all inputs exist (no interpolation). Each observation carries `derived: true` and the
formula, and the provenance panel states the modification as the ECB's terms require.

## 9. Economic Conditions Score (platform construction — not an official statistic)

Implemented in `backend/app/analytics/score.py`, served by `GET /api/score?weights=growth:1,labour:1,prices:1,financial:1`.

| Pillar | Component | Source series | Transform | Direction |
|---|---|---|---|---|
| Growth | Monthly GDP 3m/3m | ONS ECY2 | % change of latest 3-month average on previous 3 months (calendar-aligned) | higher better |
| Growth | Retail sales volume y/y | ONS J5EK | % change on same month a year earlier | higher better |
| Labour | Unemployment rate | ONS MGSX | level | lower better |
| Labour | Real pay proxy | ONS KAI9 − D7G7 | regular pay growth minus CPI, same month (approximation) | higher better |
| Prices | CPI distance from target | ONS D7G7 | −\|CPI − 2\| (BoE 2% target) | closer to 2% better |
| Prices | Core CPI distance from 2% | ONS DKO8 | −\|core − 2\| | closer to 2% better |
| Financial | 2-year fixed mortgage rate | BoE IUMBV34 | level | lower better |
| Financial | Mortgage approvals | BoE LPMVTVX | level (SA) | higher better |

Steps: orient → standardise each component over the base window (2006-01 to latest) → pillar = mean of
component z → composite = weighted mean of available pillar z (default equal weights; adjustable) → score =
100 × Φ(z). 50 = historical average. A month is scored only with ≥3 pillars; a component's latest value may be
carried forward ≤3 months (flagged ↻). Contributions (z units) sum exactly to the composite z. Only real
observations are used — never demo data.

"Live": recomputed on every request from the latest retrieved data; the UI refreshes it every minute, and the
worker's release-aware polling fetches ONS inputs within ~15 minutes of their announced 07:00 publication.

Caveats: component choice, direction and weights are judgements; history uses current (revised) vintages;
full-window standardisation means past values shift slightly as data arrive; the score is descriptive, not a
forecast, and implies no causation.
