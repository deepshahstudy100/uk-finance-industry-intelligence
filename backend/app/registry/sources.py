"""Central source registry.

Every entry was checked against the publisher's live endpoint and documentation on 2026-10-26.
`verification` records what was checked so the claim can be audited; re-run
`python -m app.cli verify` to re-check endpoints. Nothing here asserts real-time delivery unless
the publisher documents it (only NESO Carbon Intensity publishes half-hourly data).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

OGL = "Open Government Licence v3.0"
OGL_URL = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"


@dataclass(frozen=True)
class RateLimit:
    requests: int
    per_seconds: float
    documented: bool  # True = limit published by the source; False = our conservative self-imposed limit
    note: str = ""


@dataclass(frozen=True)
class SourceDef:
    id: str
    name: str
    publisher: str
    homepage: str
    docs_url: str
    api_base: str
    licence: str
    licence_url: str
    attribution: str
    auth: str  # none | optional_free_key | free_key_required
    rate_limit: RateLimit
    update_frequency: str
    latency_class: str  # official_release | daily_published | near_real_time | snapshot | on_demand
    refresh_minutes: int  # how often the scheduler polls (within documented limits)
    stale_after_hours: int  # our copy is "stale" if no successful retrieval within this window
    verification: str
    caveats: list[str] = field(default_factory=list)
    enabled_by_default: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


SOURCES: dict[str, SourceDef] = {
    s.id: s
    for s in [
        SourceDef(
            id="ons",
            name="ONS time series (website JSON) and search API",
            publisher="Office for National Statistics",
            homepage="https://www.ons.gov.uk",
            docs_url="https://developer.ons.gov.uk/",
            api_base="https://www.ons.gov.uk/{uri}/data ; https://api.beta.ons.gov.uk/v1/search",
            licence=OGL,
            licence_url=OGL_URL,
            attribution="Source: Office for National Statistics licensed under the Open Government Licence v3.0",
            auth="none",
            rate_limit=RateLimit(
                120, 10, True, "Documented: 120 req/10 s and 200 req/min (all assets); 429 with Retry-After"
            ),
            update_frequency="Per release calendar (monthly/quarterly; 07:00 UK time on release days)",
            latency_class="official_release",
            refresh_minutes=360,
            stale_after_hours=36,
            verification=(
                "2026-10-26: GET /economy/inflationandpriceindices/timeseries/d7g7/mm23/data returned 200 JSON with "
                "description.releaseDate, nextRelease, months[], quarters[], years[] and versions[] (revision "
                "history). CDID->URI resolved via api.beta.ons.gov.uk/v1/search?q={cdid}&content_type=timeseries. "
                "Limits from developer.ons.gov.uk/bots."
            ),
            caveats=[
                "The legacy api.ons.gov.uk timeseries API returns 404 with the message that it was fully retired on 25/11/2024 (checked 2026-10-26); the website /data JSON is used instead.",
                "Latest periods are subject to revision under the ONS revisions policy.",
            ],
        ),
        SourceDef(
            id="boe",
            name="Bank of England Interactive Statistical Database (IADB)",
            publisher="Bank of England",
            homepage="https://www.bankofengland.co.uk/boeapps/database/",
            docs_url="https://www.bankofengland.co.uk/boeapps/database/Help.asp",
            api_base="https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes",
            licence=OGL + " (excluding selected third-party exchange-rate data)",
            licence_url="https://www.bankofengland.co.uk/legal",
            attribution="Bank of England Database, licensed under the Open Government Licence v3.0. "
            "SONIA data licensed under the OGL v3.0 and copyright the Governor and Company of the Bank of England.",
            auth="none",
            rate_limit=RateLimit(1, 2.0, False, "No published limit; self-imposed 1 request / 2 s"),
            update_frequency="Daily series ~1 business day after the observation date; monthly series per calendar",
            latency_class="daily_published",
            refresh_minutes=360,
            stale_after_hours=48,
            verification=(
                "2026-10-26: CSV with SeriesCodes=IUDBEDR,IUDSOIA,IUDSNPY,IUDMNPY,IUDLNPY,IUMBV34,IUMBV42,LPMVTVX "
                "returned DATE,<code> columns. Unknown codes redirect to ErrorPage.asp (detected and rejected). "
                "Licence: bankofengland.co.uk/legal."
            ),
            caveats=[
                "Spot exchange rates (XUDL*) may contain LSEG/Bloomberg content whose redistribution is restricted; "
                "they are disabled by default (UKINTEL_ENABLE_BOE_FX). ECB reference rates are used instead.",
                "Gilt yields are BoE yield-curve estimates (end of day), not traded quotes.",
            ],
        ),
        SourceDef(
            id="ecb",
            name="ECB Data Portal - euro foreign exchange reference rates (EXR)",
            publisher="European Central Bank",
            homepage="https://data.ecb.europa.eu/",
            docs_url="https://data.ecb.europa.eu/help/api/overview",
            api_base="https://data-api.ecb.europa.eu/service/data/EXR/",
            licence="ECB reuse terms: free reuse with source attribution; modifications must be stated",
            licence_url="https://www.ecb.europa.eu/services/disclaimer/html/index.en.html",
            attribution="Source: European Central Bank (ECB). Sterling crosses are derived by this platform.",
            auth="none",
            rate_limit=RateLimit(1, 1.0, False, "No published limit; self-imposed 1 request / s"),
            update_frequency="Working days around 16:00 CET (reference rates, for information purposes only)",
            latency_class="daily_published",
            refresh_minutes=360,
            stale_after_hours=72,
            verification="2026-10-26: EXR/D.GBP+USD+JPY.EUR.SP00.A?format=csvdata returned KEY,...,TIME_PERIOD,OBS_VALUE.",
            caveats=["Reference rates are not transaction rates. GBP/USD and GBP/JPY are derived (cross rates)."],
        ),
        SourceDef(
            id="nomis",
            name="NOMIS API (labour market, earnings, business counts)",
            publisher="Office for National Statistics / Durham University (NOMIS)",
            homepage="https://www.nomisweb.co.uk",
            docs_url="https://www.nomisweb.co.uk/api/v01/help",
            api_base="https://www.nomisweb.co.uk/api/v01/dataset/",
            licence=OGL,
            licence_url=OGL_URL,
            attribution="Source: ONS via NOMIS, licensed under the Open Government Licence v3.0",
            auth="optional_free_key",
            rate_limit=RateLimit(
                2, 1.0, False, "Documented 25,000-cell limit per guest request (uid lifts it); self-imposed 2 req/s"
            ),
            update_frequency="Monthly (claimant count), quarterly (APS, workforce jobs), annual (ASHE, business counts)",
            latency_class="official_release",
            refresh_minutes=1440,
            stale_after_hours=96,
            verification=(
                "2026-10-26: NM_17_5 (APS), NM_162_1 (claimant count), NM_30_1 (ASHE), NM_142_1 (UK Business "
                "Counts), NM_130_1 (workforce jobs) CSV queries returned data for TYPE480 regions, TYPE499 "
                "countries and TYPE424 local authorities (361)."
            ),
            caveats=[
                "APS local-authority estimates have wide confidence intervals; they are displayed.",
                "Claimant count is affected by Universal Credit rollout; not a measure of ILO unemployment.",
            ],
        ),
        SourceDef(
            id="land_registry",
            name="HM Land Registry linked data (UK HPI and Price Paid) SPARQL",
            publisher="HM Land Registry",
            homepage="https://landregistry.data.gov.uk/",
            docs_url="https://landregistry.data.gov.uk/app/qonsole",
            api_base="https://landregistry.data.gov.uk/landregistry/query",
            licence=OGL,
            licence_url="https://www.gov.uk/guidance/about-the-price-paid-data",
            attribution="Contains HM Land Registry data (c) Crown copyright and database right. "
            "Licensed under the Open Government Licence v3.0.",
            auth="none",
            rate_limit=RateLimit(1, 1.0, False, "No published limit; self-imposed 1 query / s"),
            update_frequency="UK HPI monthly (~2-month lag); Price Paid monthly (20th working day)",
            latency_class="official_release",
            refresh_minutes=1440,
            stale_after_hours=96,
            verification=(
                "2026-10-26: SPARQL ukhpi:refRegion/refMonth/averagePrice/housePriceIndex returned UK, regions, "
                "nations (latest month 2026-08). Price Paid lrppi:pricePaid by lrcommon:district returned rows."
            ),
            caveats=[
                "Recent UK HPI months are revised as more registrations arrive.",
                "Price Paid excludes some transaction types (e.g. right-to-buy, non-market) - see PPD guidance.",
                "UK HPI for Scotland/NI is compiled by RoS/LPS using different data.",
            ],
        ),
        SourceDef(
            id="hmrc_ots",
            name="HMRC Overseas Trade Statistics (uktradeinfo OData API)",
            publisher="HM Revenue & Customs",
            homepage="https://www.uktradeinfo.com/",
            docs_url="https://www.uktradeinfo.com/api-documentation/",
            api_base="https://api.uktradeinfo.com/",
            licence=OGL,
            licence_url=OGL_URL,
            attribution="Source: HMRC Overseas Trade Statistics, licensed under the Open Government Licence v3.0",
            auth="none",
            rate_limit=RateLimit(60, 60, True, "Documented 60 requests/min; 40,000 rows per response"),
            update_frequency="Monthly release (~6 weeks after reference month)",
            latency_class="official_release",
            refresh_minutes=1440,
            stale_after_hours=96,
            verification=(
                "2026-10-26: /OTS?$apply=filter(MonthId eq 202606)/groupby((FlowTypeId),aggregate(Value with sum "
                "as Total)) returned totals; /FlowType, /Country, /SITC returned lookups. $orderby is not an "
                "allowed operation (request rejected) - only $select,$expand,$filter,$top,$apply,$count,$format."
            ),
            caveats=[
                "Goods only, not seasonally adjusted, current prices (GBP). Differs from ONS balance-of-payments "
                "trade (which adjusts for coverage/valuation and includes services).",
            ],
        ),
        SourceDef(
            id="neso_carbon",
            name="NESO Carbon Intensity API",
            publisher="National Energy System Operator (with EDF Europe, Oxford University, WWF)",
            homepage="https://carbonintensity.org.uk/",
            docs_url="https://carbon-intensity.github.io/api-definitions/",
            api_base="https://api.carbonintensity.org.uk/",
            licence="CC BY 4.0",
            licence_url="https://creativecommons.org/licenses/by/4.0/",
            attribution="Carbon Intensity API, National Energy System Operator, CC BY 4.0",
            auth="none",
            rate_limit=RateLimit(1, 1.0, False, "No published limit; self-imposed 1 req/s, polled every 30 min"),
            update_frequency="Half-hourly (forecast refreshed every 30 minutes; actual intensity estimated)",
            latency_class="near_real_time",
            refresh_minutes=30,
            stale_after_hours=3,
            verification="2026-10-26: GET /generation returned current half-hour generation mix (%).",
            caveats=["GB only (excludes Northern Ireland). Values are modelled estimates, not metered totals."],
        ),
        SourceDef(
            id="desnz_fuel",
            name="DESNZ weekly road fuel prices (via GOV.UK Content API)",
            publisher="Department for Energy Security and Net Zero",
            homepage="https://www.gov.uk/government/statistics/weekly-road-fuel-prices",
            docs_url="https://content-api.publishing.service.gov.uk/",
            api_base="https://www.gov.uk/api/content/government/statistics/weekly-road-fuel-prices",
            licence=OGL,
            licence_url=OGL_URL,
            attribution="Source: DESNZ weekly road fuel prices, licensed under the Open Government Licence v3.0",
            auth="none",
            rate_limit=RateLimit(1, 1.0, False, "Self-imposed 1 req/s"),
            update_frequency="Weekly (published Tuesdays for Monday prices)",
            latency_class="official_release",
            refresh_minutes=720,
            stale_after_hours=72,
            verification=(
                "2026-10-26: Content API listed attachment 'Weekly road fuel prices (CSV) 2018 to 2026'; CSV header "
                "Date, ULSP/ULSD pump price p/litre, duty, VAT. Attachment URL is discovered each run (it changes)."
            ),
            caveats=["UK average pump prices; not regional."],
        ),
        SourceDef(
            id="dmo",
            name="UK Debt Management Office data reports (XML)",
            publisher="UK Debt Management Office",
            homepage="https://www.dmo.gov.uk/data/",
            docs_url="https://www.dmo.gov.uk/data/",
            api_base="https://www.dmo.gov.uk/data/XmlDataReport?reportCode=D1A",
            licence=OGL,
            licence_url=OGL_URL,
            attribution="Source: UK Debt Management Office, licensed under the Open Government Licence v3.0",
            auth="none",
            rate_limit=RateLimit(1, 5.0, False, "Self-imposed 1 request / 5 s; site uses bot protection"),
            update_frequency="Daily snapshot of gilts in issue (close of business)",
            latency_class="snapshot",
            refresh_minutes=1440,
            stale_after_hours=96,
            verification=(
                "2026-10-26: reportCode=D1A returned <View_GILTS_IN_ISSUE CLOSE_OF_BUSINESS_DATE INSTRUMENT_TYPE "
                "MATURITY_BRACKET ... TOTAL_AMOUNT_IN_ISSUE>. OGL reuse statement taken from DMO publications "
                "(copyright page is behind bot protection and could not be fetched programmatically)."
            ),
            caveats=["Nominal amounts (GBP m). Index-linked uplift reported separately.",
                     "On 2026-10-26 requests with this platform's honest (non-browser) User-Agent were redirected "
                     "to a bot-protection challenge (HTTP 302). This platform does not spoof browsers or bypass "
                     "bot protection, so this series is usually shown as unavailable. ONS public sector net debt "
                     "(HF6W/HF6X) is used for debt totals instead."],
        ),
        SourceDef(
            id="companies_house",
            name="Companies House Public Data API",
            publisher="Companies House",
            homepage="https://developer.company-information.service.gov.uk/",
            docs_url="https://developer-specs.company-information.service.gov.uk/",
            api_base="https://api.company-information.service.gov.uk/",
            licence="Companies House public register data (free); developer guidelines apply",
            licence_url="https://developer.company-information.service.gov.uk/developer-guidelines",
            attribution="Contains Companies House data",
            auth="free_key_required",
            rate_limit=RateLimit(600, 300, True, "Documented 600 requests per 5 minutes; 429 for remainder of window"),
            update_frequency="Continuously updated register (queried on demand)",
            latency_class="on_demand",
            refresh_minutes=0,
            stale_after_hours=0,
            verification="2026-10-26: unauthenticated request returned 401 'Empty Authorization header' as documented.",
            caveats=["Requires a free API key (UKINTEL_COMPANIES_HOUSE_API_KEY). Officer personal data is not shown."],
        ),
        SourceDef(
            id="ons_geography",
            name="ONS Open Geography Portal (boundaries and lookups)",
            publisher="Office for National Statistics",
            homepage="https://geoportal.statistics.gov.uk/",
            docs_url="https://geoportal.statistics.gov.uk/",
            api_base="https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/",
            licence=OGL,
            licence_url=OGL_URL,
            attribution="Source: Office for National Statistics licensed under the Open Government Licence v3.0. "
            "Contains OS data (c) Crown copyright and database right.",
            auth="none",
            rate_limit=RateLimit(1, 1.0, False, "Self-imposed 1 req/s"),
            update_frequency="Boundaries change annually",
            latency_class="snapshot",
            refresh_minutes=60 * 24 * 30,
            stale_after_hours=24 * 120,
            verification=(
                "2026-10-26: ITL1_JAN_2025_UK_BUC (12 features), LAD_MAY_2025_UK_BUC (361 features) and "
                "ITL125_ITL225_ITL325_LAU125_LAD25_UK_LU (362 rows) FeatureServer queries returned GeoJSON/JSON."
            ),
        ),
    ]
}


NOT_INTEGRATED = [
    {
        "name": "Equity indices (FTSE 100/250)",
        "reason": "FTSE Russell index data is proprietary. No free source with verified redistribution terms "
        "was found, so no equity index is shown. Unofficial scraping is not used.",
    },
    {
        "name": "Bank of England spot exchange rates (XUDL*)",
        "reason": "May contain LSEG/Bloomberg content whose redistribution is restricted. Disabled by default.",
    },
    {
        "name": "ONS producer price indices (MM22)",
        "reason": "Series checked on 2026-10-26 (e.g. GB7S) had no observations after 2025 JAN, so it is not "
        "presented as current.",
    },
    {
        "name": "DESNZ Energy Trends (Excel workbooks)",
        "reason": "Published as multi-sheet spreadsheets with changing layouts; not yet parsed. Weekly fuel prices "
        "and NESO generation mix are integrated instead.",
    },
]
