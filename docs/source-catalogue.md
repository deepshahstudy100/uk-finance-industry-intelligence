# Source catalogue

Generated from `backend/app/registry/` by `python -m app.cli catalogue`. Do not edit by hand.

## Sources

### Office for National Statistics — ONS time series (website JSON) and search API (`ons`)

- **Endpoint:** `https://www.ons.gov.uk/{uri}/data ; https://api.beta.ons.gov.uk/v1/search`
- **Documentation:** https://developer.ons.gov.uk/
- **Licence:** [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
- **Attribution:** Source: Office for National Statistics licensed under the Open Government Licence v3.0
- **Authentication:** none
- **Rate limit:** Documented: 120 req/10 s and 200 req/min (all assets); 429 with Retry-After (documented by source)
- **Update frequency:** Per release calendar (monthly/quarterly; 07:00 UK time on release days)
- **Latency class:** official_release
- **Polling:** every 360 min; stale after 36 h
- **Verification:** 2026-10-26: GET /economy/inflationandpriceindices/timeseries/d7g7/mm23/data returned 200 JSON with description.releaseDate, nextRelease, months[], quarters[], years[] and versions[] (revision history). CDID->URI resolved via api.beta.ons.gov.uk/v1/search?q={cdid}&content_type=timeseries. Limits from developer.ons.gov.uk/bots.
- **Caveat:** The legacy api.ons.gov.uk timeseries API returns 404 with the message that it was fully retired on 25/11/2024 (checked 2026-10-26); the website /data JSON is used instead.
- **Caveat:** Latest periods are subject to revision under the ONS revisions policy.

### Bank of England — Bank of England Interactive Statistical Database (IADB) (`boe`)

- **Endpoint:** `https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes`
- **Documentation:** https://www.bankofengland.co.uk/boeapps/database/Help.asp
- **Licence:** [Open Government Licence v3.0 (excluding selected third-party exchange-rate data)](https://www.bankofengland.co.uk/legal)
- **Attribution:** Bank of England Database, licensed under the Open Government Licence v3.0. SONIA data licensed under the OGL v3.0 and copyright the Governor and Company of the Bank of England.
- **Authentication:** none
- **Rate limit:** No published limit; self-imposed 1 request / 2 s (self-imposed)
- **Update frequency:** Daily series ~1 business day after the observation date; monthly series per calendar
- **Latency class:** daily_published
- **Polling:** every 360 min; stale after 48 h
- **Verification:** 2026-10-26: CSV with SeriesCodes=IUDBEDR,IUDSOIA,IUDSNPY,IUDMNPY,IUDLNPY,IUMBV34,IUMBV42,LPMVTVX returned DATE,<code> columns. Unknown codes redirect to ErrorPage.asp (detected and rejected). Licence: bankofengland.co.uk/legal.
- **Caveat:** Spot exchange rates (XUDL*) may contain LSEG/Bloomberg content whose redistribution is restricted; they are disabled by default (UKINTEL_ENABLE_BOE_FX). ECB reference rates are used instead.
- **Caveat:** Gilt yields are BoE yield-curve estimates (end of day), not traded quotes.

### European Central Bank — ECB Data Portal - euro foreign exchange reference rates (EXR) (`ecb`)

- **Endpoint:** `https://data-api.ecb.europa.eu/service/data/EXR/`
- **Documentation:** https://data.ecb.europa.eu/help/api/overview
- **Licence:** [ECB reuse terms: free reuse with source attribution; modifications must be stated](https://www.ecb.europa.eu/services/disclaimer/html/index.en.html)
- **Attribution:** Source: European Central Bank (ECB). Sterling crosses are derived by this platform.
- **Authentication:** none
- **Rate limit:** No published limit; self-imposed 1 request / s (self-imposed)
- **Update frequency:** Working days around 16:00 CET (reference rates, for information purposes only)
- **Latency class:** daily_published
- **Polling:** every 360 min; stale after 72 h
- **Verification:** 2026-10-26: EXR/D.GBP+USD+JPY.EUR.SP00.A?format=csvdata returned KEY,...,TIME_PERIOD,OBS_VALUE.
- **Caveat:** Reference rates are not transaction rates. GBP/USD and GBP/JPY are derived (cross rates).

### Office for National Statistics / Durham University (NOMIS) — NOMIS API (labour market, earnings, business counts) (`nomis`)

- **Endpoint:** `https://www.nomisweb.co.uk/api/v01/dataset/`
- **Documentation:** https://www.nomisweb.co.uk/api/v01/help
- **Licence:** [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
- **Attribution:** Source: ONS via NOMIS, licensed under the Open Government Licence v3.0
- **Authentication:** optional_free_key
- **Rate limit:** Documented 25,000-cell limit per guest request (uid lifts it); self-imposed 2 req/s (self-imposed)
- **Update frequency:** Monthly (claimant count), quarterly (APS, workforce jobs), annual (ASHE, business counts)
- **Latency class:** official_release
- **Polling:** every 1440 min; stale after 96 h
- **Verification:** 2026-10-26: NM_17_5 (APS), NM_162_1 (claimant count), NM_30_1 (ASHE), NM_142_1 (UK Business Counts), NM_130_1 (workforce jobs) CSV queries returned data for TYPE480 regions, TYPE499 countries and TYPE424 local authorities (361).
- **Caveat:** APS local-authority estimates have wide confidence intervals; they are displayed.
- **Caveat:** Claimant count is affected by Universal Credit rollout; not a measure of ILO unemployment.

### HM Land Registry — HM Land Registry linked data (UK HPI and Price Paid) SPARQL (`land_registry`)

- **Endpoint:** `https://landregistry.data.gov.uk/landregistry/query`
- **Documentation:** https://landregistry.data.gov.uk/app/qonsole
- **Licence:** [Open Government Licence v3.0](https://www.gov.uk/guidance/about-the-price-paid-data)
- **Attribution:** Contains HM Land Registry data (c) Crown copyright and database right. Licensed under the Open Government Licence v3.0.
- **Authentication:** none
- **Rate limit:** No published limit; self-imposed 1 query / s (self-imposed)
- **Update frequency:** UK HPI monthly (~2-month lag); Price Paid monthly (20th working day)
- **Latency class:** official_release
- **Polling:** every 1440 min; stale after 96 h
- **Verification:** 2026-10-26: SPARQL ukhpi:refRegion/refMonth/averagePrice/housePriceIndex returned UK, regions, nations (latest month 2026-08). Price Paid lrppi:pricePaid by lrcommon:district returned rows.
- **Caveat:** Recent UK HPI months are revised as more registrations arrive.
- **Caveat:** Price Paid excludes some transaction types (e.g. right-to-buy, non-market) - see PPD guidance.
- **Caveat:** UK HPI for Scotland/NI is compiled by RoS/LPS using different data.

### HM Revenue & Customs — HMRC Overseas Trade Statistics (uktradeinfo OData API) (`hmrc_ots`)

- **Endpoint:** `https://api.uktradeinfo.com/`
- **Documentation:** https://www.uktradeinfo.com/api-documentation/
- **Licence:** [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
- **Attribution:** Source: HMRC Overseas Trade Statistics, licensed under the Open Government Licence v3.0
- **Authentication:** none
- **Rate limit:** Documented 60 requests/min; 40,000 rows per response (documented by source)
- **Update frequency:** Monthly release (~6 weeks after reference month)
- **Latency class:** official_release
- **Polling:** every 1440 min; stale after 96 h
- **Verification:** 2026-10-26: /OTS?$apply=filter(MonthId eq 202606)/groupby((FlowTypeId),aggregate(Value with sum as Total)) returned totals; /FlowType, /Country, /SITC returned lookups. $orderby is not an allowed operation (request rejected) - only $select,$expand,$filter,$top,$apply,$count,$format.
- **Caveat:** Goods only, not seasonally adjusted, current prices (GBP). Differs from ONS balance-of-payments trade (which adjusts for coverage/valuation and includes services).

### National Energy System Operator (with EDF Europe, Oxford University, WWF) — NESO Carbon Intensity API (`neso_carbon`)

- **Endpoint:** `https://api.carbonintensity.org.uk/`
- **Documentation:** https://carbon-intensity.github.io/api-definitions/
- **Licence:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- **Attribution:** Carbon Intensity API, National Energy System Operator, CC BY 4.0
- **Authentication:** none
- **Rate limit:** No published limit; self-imposed 1 req/s, polled every 30 min (self-imposed)
- **Update frequency:** Half-hourly (forecast refreshed every 30 minutes; actual intensity estimated)
- **Latency class:** near_real_time
- **Polling:** every 30 min; stale after 3 h
- **Verification:** 2026-10-26: GET /generation returned current half-hour generation mix (%).
- **Caveat:** GB only (excludes Northern Ireland). Values are modelled estimates, not metered totals.

### Department for Energy Security and Net Zero — DESNZ weekly road fuel prices (via GOV.UK Content API) (`desnz_fuel`)

- **Endpoint:** `https://www.gov.uk/api/content/government/statistics/weekly-road-fuel-prices`
- **Documentation:** https://content-api.publishing.service.gov.uk/
- **Licence:** [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
- **Attribution:** Source: DESNZ weekly road fuel prices, licensed under the Open Government Licence v3.0
- **Authentication:** none
- **Rate limit:** Self-imposed 1 req/s (self-imposed)
- **Update frequency:** Weekly (published Tuesdays for Monday prices)
- **Latency class:** official_release
- **Polling:** every 720 min; stale after 72 h
- **Verification:** 2026-10-26: Content API listed attachment 'Weekly road fuel prices (CSV) 2018 to 2026'; CSV header Date, ULSP/ULSD pump price p/litre, duty, VAT. Attachment URL is discovered each run (it changes).
- **Caveat:** UK average pump prices; not regional.

### UK Debt Management Office — UK Debt Management Office data reports (XML) (`dmo`)

- **Endpoint:** `https://www.dmo.gov.uk/data/XmlDataReport?reportCode=D1A`
- **Documentation:** https://www.dmo.gov.uk/data/
- **Licence:** [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
- **Attribution:** Source: UK Debt Management Office, licensed under the Open Government Licence v3.0
- **Authentication:** none
- **Rate limit:** Self-imposed 1 request / 5 s; site uses bot protection (self-imposed)
- **Update frequency:** Daily snapshot of gilts in issue (close of business)
- **Latency class:** snapshot
- **Polling:** every 1440 min; stale after 96 h
- **Verification:** 2026-10-26: reportCode=D1A returned <View_GILTS_IN_ISSUE CLOSE_OF_BUSINESS_DATE INSTRUMENT_TYPE MATURITY_BRACKET ... TOTAL_AMOUNT_IN_ISSUE>. OGL reuse statement taken from DMO publications (copyright page is behind bot protection and could not be fetched programmatically).
- **Caveat:** Nominal amounts (GBP m). Index-linked uplift reported separately.
- **Caveat:** On 2026-10-26 requests with this platform's honest (non-browser) User-Agent were redirected to a bot-protection challenge (HTTP 302). This platform does not spoof browsers or bypass bot protection, so this series is usually shown as unavailable. ONS public sector net debt (HF6W/HF6X) is used for debt totals instead.

### Companies House — Companies House Public Data API (`companies_house`)

- **Endpoint:** `https://api.company-information.service.gov.uk/`
- **Documentation:** https://developer-specs.company-information.service.gov.uk/
- **Licence:** [Companies House public register data (free); developer guidelines apply](https://developer.company-information.service.gov.uk/developer-guidelines)
- **Attribution:** Contains Companies House data
- **Authentication:** free_key_required
- **Rate limit:** Documented 600 requests per 5 minutes; 429 for remainder of window (documented by source)
- **Update frequency:** Continuously updated register (queried on demand)
- **Latency class:** on_demand
- **Polling:** on demand only
- **Verification:** 2026-10-26: unauthenticated request returned 401 'Empty Authorization header' as documented.
- **Caveat:** Requires a free API key (UKINTEL_COMPANIES_HOUSE_API_KEY). Officer personal data is not shown.

### Office for National Statistics — ONS Open Geography Portal (boundaries and lookups) (`ons_geography`)

- **Endpoint:** `https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/`
- **Documentation:** https://geoportal.statistics.gov.uk/
- **Licence:** [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
- **Attribution:** Source: Office for National Statistics licensed under the Open Government Licence v3.0. Contains OS data (c) Crown copyright and database right.
- **Authentication:** none
- **Rate limit:** Self-imposed 1 req/s (self-imposed)
- **Update frequency:** Boundaries change annually
- **Latency class:** snapshot
- **Polling:** every 43200 min; stale after 2880 h
- **Verification:** 2026-10-26: ITL1_JAN_2025_UK_BUC (12 features), LAD_MAY_2025_UK_BUC (361 features) and ITL125_ITL225_ITL325_LAU125_LAD25_UK_LU (362 rows) FeatureServer queries returned GeoJSON/JSON.

## Series

| ID | Title | Source | Identifier | Unit | Measure | Freq | SA | Geography | Breakdown |
|---|---|---|---|---|---|---|---|---|---|
| `gdp_qoq` | GDP growth, quarter on quarter | ons | `IHYQ/QNA` | % | growth_rate | Q | SA | uk |  |
| `gdp_yoy` | GDP growth, year on year | ons | `IHYR/QNA` | % | growth_rate | Q | SA | uk |  |
| `gdp_level` | GDP, chained volume measure | ons | `ABMI/QNA` | £m | level | Q | SA | uk |  |
| `gdp_monthly_index` | Monthly GDP (gross value added) index | ons | `ECY2/MGDP` | index | index | M | SA | uk |  |
| `hfce` | Household final consumption expenditure | ons | `ABJR/QNA` | £m | level | Q | SA | uk |  |
| `productivity_oph` | Labour productivity: output per hour | ons | `LZVB/PRDY` | index | index | Q | SA | uk |  |
| `retail_sales_volume` | Retail sales volume (incl. fuel) | ons | `J5EK/DRSI` | index | index | M | SA | uk | G |
| `iop_production` | Index of Production (B-E) | ons | `K222/DIOP` | index | index | M | SA | uk |  |
| `iop_manufacturing` | Manufacturing output (IoP section C) | ons | `K22A/DIOP` | index | index | M | SA | uk | C |
| `ios_services` | Index of Services | ons | `S2KU/IOS1` | index | index | M | SA | uk |  |
| `cpi_yoy` | CPI inflation (12-month rate) | ons | `D7G7/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpih_yoy` | CPIH inflation (12-month rate) | ons | `L55O/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_index` | CPI index, all items | ons | `D7BT/MM23` | index (2015=100) | index | M | NSA | uk |  |
| `cpi_core_yoy` | Core CPI inflation | ons | `DKO8/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_goods_yoy` | CPI goods inflation | ons | `D7NM/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_services_yoy` | CPI services inflation | ons | `D7NN/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_div_01` | CPI 01: Food and non-alcoholic beverages | ons | `D7G8/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_div_02` | CPI 02: Alcoholic beverages and tobacco | ons | `D7G9/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_div_03` | CPI 03: Clothing and footwear | ons | `D7GA/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_div_04` | CPI 04: Housing, water, electricity, gas and other fuels | ons | `D7GB/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_div_05` | CPI 05: Furniture, household equipment and maintenance | ons | `D7GC/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_div_06` | CPI 06: Health | ons | `D7GD/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_div_07` | CPI 07: Transport | ons | `D7GE/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_div_08` | CPI 08: Communication | ons | `D7GF/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_div_09` | CPI 09: Recreation and culture | ons | `D7GG/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_div_10` | CPI 10: Education | ons | `D7GH/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_div_11` | CPI 11: Restaurants and hotels | ons | `D7GI/MM23` | % | growth_rate | M | NSA | uk |  |
| `cpi_div_12` | CPI 12: Miscellaneous goods and services | ons | `D7GJ/MM23` | % | growth_rate | M | NSA | uk |  |
| `unemployment_rate` | Unemployment rate (16+) | ons | `MGSX/LMS` | % | rate | M | SA | uk |  |
| `employment_rate` | Employment rate (16-64) | ons | `LF24/LMS` | % | rate | M | SA | uk |  |
| `inactivity_rate` | Economic inactivity rate (16-64) | ons | `LF2S/LMS` | % | rate | M | SA | uk |  |
| `awe_total_growth` | Pay growth: total pay (AWE) | ons | `KAC3/LMS` | % | growth_rate | M | SA | uk |  |
| `awe_regular_growth` | Pay growth: regular pay (AWE) | ons | `KAI9/LMS` | % | growth_rate | M | SA | uk |  |
| `vacancies` | Job vacancies | ons | `AP2Y/LMS` | thousands | level | M | SA | uk |  |
| `psnb_ex` | Public sector net borrowing (ex. banks) | ons | `J5II/PUSF` | £m | level | M | NSA | uk |  |
| `psnd_ex` | Public sector net debt (ex. banks) | ons | `HF6W/PUSF` | £bn | level | M | NSA | uk |  |
| `psnd_ex_gdp` | Public sector net debt, % of GDP | ons | `HF6X/PUSF` | % of GDP | share | M | NSA | uk |  |
| `trade_balance` | Trade balance (goods and services) | ons | `IKBJ/MRET` | £m | level | M | SA | uk |  |
| `exports_total` | Exports (goods and services) | ons | `IKBH/MRET` | £m | level | M | SA | uk |  |
| `imports_total` | Imports (goods and services) | ons | `IKBI/MRET` | £m | level | M | SA | uk |  |
| `gva_A` | Output: Agriculture, forestry and fishing | ons | `ECY3/MGDP` | index | index | M | SA | uk | A |
| `gva_B` | Output: Mining and quarrying | ons | `ECY5/MGDP` | index | index | M | SA | uk | B |
| `gva_C` | Output: Manufacturing | ons | `ECY6/MGDP` | index | index | M | SA | uk | C |
| `gva_D` | Output: Electricity, gas, steam and air conditioning supply | ons | `ECY7/MGDP` | index | index | M | SA | uk | D |
| `gva_E` | Output: Water supply; sewerage and waste management | ons | `ECY8/MGDP` | index | index | M | SA | uk | E |
| `gva_F` | Output: Construction | ons | `ECY9/MGDP` | index | index | M | SA | uk | F |
| `gva_G` | Output: Wholesale and retail trade; repair of motor vehicles | ons | `ECYD/MGDP` | index | index | M | SA | uk | G |
| `gva_H` | Output: Transportation and storage | ons | `ECYG/MGDP` | index | index | M | SA | uk | H |
| `gva_I` | Output: Accommodation and food service activities | ons | `ECYH/MGDP` | index | index | M | SA | uk | I |
| `gva_J` | Output: Information and communication | ons | `ECYI/MGDP` | index | index | M | SA | uk | J |
| `gva_K` | Output: Financial and insurance activities | ons | `ECYJ/MGDP` | index | index | M | SA | uk | K |
| `gva_L` | Output: Real estate activities | ons | `ECYK/MGDP` | index | index | M | SA | uk | L |
| `gva_M` | Output: Professional, scientific and technical activities | ons | `ECYL/MGDP` | index | index | M | SA | uk | M |
| `gva_N` | Output: Administrative and support service activities | ons | `ECYP/MGDP` | index | index | M | SA | uk | N |
| `gva_O` | Output: Public administration and defence | ons | `ECYQ/MGDP` | index | index | M | SA | uk | O |
| `gva_P` | Output: Education | ons | `ECYR/MGDP` | index | index | M | SA | uk | P |
| `gva_Q` | Output: Human health and social work activities | ons | `ECYS/MGDP` | index | index | M | SA | uk | Q |
| `gva_R` | Output: Arts, entertainment and recreation | ons | `ECYT/MGDP` | index | index | M | SA | uk | R |
| `gva_S` | Output: Other service activities | ons | `ECYU/MGDP` | index | index | M | SA | uk | S |
| `bank_rate` | Bank Rate | boe | `IUDBEDR` | % | rate | D | n/a | uk |  |
| `sonia` | SONIA | boe | `IUDSOIA` | % | rate | D | n/a | uk |  |
| `gilt_5y` | 5-year gilt yield (nominal par) | boe | `IUDSNPY` | % | rate | D | n/a | uk |  |
| `gilt_10y` | 10-year gilt yield (nominal par) | boe | `IUDMNPY` | % | rate | D | n/a | uk |  |
| `gilt_20y` | 20-year gilt yield (nominal par) | boe | `IUDLNPY` | % | rate | D | n/a | uk |  |
| `mortgage_2y_75` | 2-year fixed mortgage rate (75% LTV) | boe | `IUMBV34` | % | rate | M | NSA | uk |  |
| `mortgage_5y_75` | 5-year fixed mortgage rate (75% LTV) | boe | `IUMBV42` | % | rate | M | NSA | uk |  |
| `mortgage_approvals` | Mortgage approvals for house purchase | boe | `LPMVTVX` | number | level | M | SA | uk |  |
| `boe_gbp_usd` | BoE spot: US$ into sterling | boe | `XUDLUSS` | USD per GBP | price | D | n/a | uk (disabled) |  |
| `ecb_gbp_per_eur` | ECB reference rate: GBP per EUR | ecb | `D.GBP.EUR.SP00.A` | GBP per EUR | price | D | n/a | uk |  |
| `ecb_usd_per_eur` | ECB reference rate: USD per EUR | ecb | `D.USD.EUR.SP00.A` | USD per EUR | price | D | n/a | uk |  |
| `ecb_jpy_per_eur` | ECB reference rate: JPY per EUR | ecb | `D.JPY.EUR.SP00.A` | JPY per EUR | price | D | n/a | uk |  |
| `fx_gbp_eur` | GBP/EUR (euros per pound) | ecb | `derived` | EUR per GBP | price | D | n/a | uk |  |
| `fx_gbp_usd` | GBP/USD (dollars per pound) | ecb | `derived` | USD per GBP | price | D | n/a | uk |  |
| `fx_gbp_jpy` | GBP/JPY (yen per pound) | ecb | `derived` | JPY per GBP | price | D | n/a | uk |  |
| `aps_unemployment_rate` | Unemployment rate (APS, regional) | nomis | `NM_17_5:83` | % | rate | Q | NSA | itl1+nation+lad |  |
| `aps_employment_rate` | Employment rate 16-64 (APS, regional) | nomis | `NM_17_5:45` | % | rate | Q | NSA | itl1+nation+lad |  |
| `claimant_rate` | Claimant count rate | nomis | `NM_162_1:2` | % | rate | M | NSA | itl1+nation+lad |  |
| `claimant_count` | Claimant count | nomis | `NM_162_1:1` | people | level | M | NSA | itl1+nation+lad |  |
| `ashe_weekly_pay_ft` | Median weekly pay, full-time (residence) | nomis | `NM_30_1` | £ | price | A | n/a | itl1+nation+lad |  |
| `business_counts` | Enterprises by industry (UK Business Counts) | nomis | `NM_142_1` | enterprises | level | A | n/a | itl1+nation+lad | sic_section |
| `workforce_jobs` | Workforce jobs by industry | nomis | `NM_130_1` | jobs | level | Q | SA | itl1+nation | sic_section |
| `hpi_avg_price` | Average house price (UK HPI) | land_registry | `ukhpi:averagePrice` | £ | price | M | NSA | itl1+nation |  |
| `hpi_yoy` | House price inflation (UK HPI) | land_registry | `ukhpi:percentageAnnualChange` | % | growth_rate | M | NSA | itl1+nation |  |
| `hpi_index` | House price index (UK HPI) | land_registry | `ukhpi:housePriceIndex` | index | index | M | NSA | itl1+nation |  |
| `hpi_sales_volume` | Property sales volume (UK HPI) | land_registry | `ukhpi:salesVolume` | sales | level | M | NSA | itl1+nation |  |
| `hmrc_exports_partner` | Goods exports by partner country | hmrc_ots | `OTS:exports:country` | £ | level | M | NSA | uk | partner_country |
| `hmrc_imports_partner` | Goods imports by partner country | hmrc_ots | `OTS:imports:country` | £ | level | M | NSA | uk | partner_country |
| `hmrc_exports_sitc` | Goods exports by SITC section | hmrc_ots | `OTS:exports:sitc1` | £ | level | M | NSA | uk | sitc1 |
| `hmrc_imports_sitc` | Goods imports by SITC section | hmrc_ots | `OTS:imports:sitc1` | £ | level | M | NSA | uk | sitc1 |
| `carbon_intensity` | GB grid carbon intensity | neso_carbon | `intensity` | gCO2/kWh | level | HH | n/a | gb |  |
| `generation_mix` | GB generation mix | neso_carbon | `generation` | % of generation | share | HH | n/a | gb | fuel |
| `fuel_petrol` | Unleaded petrol pump price | desnz_fuel | `ULSP` | pence per litre | price | W | n/a | uk |  |
| `fuel_diesel` | Diesel pump price | desnz_fuel | `ULSD` | pence per litre | price | W | n/a | uk |  |
| `gilts_in_issue` | Gilts in issue by maturity bracket | dmo | `D1A` | £m nominal | level | D | n/a | uk | maturity_bracket |

## Considered but not integrated

- **Equity indices (FTSE 100/250)** — FTSE Russell index data is proprietary. No free source with verified redistribution terms was found, so no equity index is shown. Unofficial scraping is not used.
- **Bank of England spot exchange rates (XUDL*)** — May contain LSEG/Bloomberg content whose redistribution is restricted. Disabled by default.
- **ONS producer price indices (MM22)** — Series checked on 2026-10-26 (e.g. GB7S) had no observations after 2025 JAN, so it is not presented as current.
- **DESNZ Energy Trends (Excel workbooks)** — Published as multi-sheet spreadsheets with changing layouts; not yet parsed. Weekly fuel prices and NESO generation mix are integrated instead.
