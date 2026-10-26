"""Series catalogue: what each metric is, where it comes from and how it may be analysed.

`measure_type` drives which transformations are statistically appropriate (see analytics/transforms.py):
  level        - amounts/counts (GBP m, jobs, enterprises): % change, abs change, indexing OK
  index        - index numbers: % change OK, abs change in index points, rebasing OK
  price        - prices (GBP, pence/litre, FX rates): % change OK
  rate         - interest/unemployment rates (%): changes in percentage points only
  growth_rate  - already a growth rate (% change): only pp differences; no % change of a % change
  share        - shares/ratios (% of GDP, % of generation): pp differences only

Identifiers (CDIDs, BoE codes, NOMIS dataset ids, SPARQL properties) were each checked live on
2026-10-26; `app.cli verify` re-checks them. ONS URIs are resolved through the ONS search API at
ingestion time (the `uri` here is the value that search returned on verification).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

SIC_SECTIONS: dict[str, str] = {
    "A": "Agriculture, forestry and fishing",
    "B": "Mining and quarrying",
    "C": "Manufacturing",
    "D": "Electricity, gas, steam and air conditioning supply",
    "E": "Water supply; sewerage and waste management",
    "F": "Construction",
    "G": "Wholesale and retail trade; repair of motor vehicles",
    "H": "Transportation and storage",
    "I": "Accommodation and food service activities",
    "J": "Information and communication",
    "K": "Financial and insurance activities",
    "L": "Real estate activities",
    "M": "Professional, scientific and technical activities",
    "N": "Administrative and support service activities",
    "O": "Public administration and defence",
    "P": "Education",
    "Q": "Human health and social work activities",
    "R": "Arts, entertainment and recreation",
    "S": "Other service activities",
    "T": "Households as employers",
    "U": "Extraterritorial organisations",
}

UK = "K02000001"


@dataclass(frozen=True)
class SeriesDef:
    id: str
    source_id: str
    source_key: str
    title: str
    category: str
    definition: str
    unit: str
    measure_type: str
    frequency: str  # HH | D | W | M | Q | A
    seasonal_adjustment: str = "n/a"  # SA | NSA | n/a
    geography: str = "uk"  # uk | gb | itl1+nation | itl1+nation+lad
    dim_kind: str | None = None  # sic_section | partner_country | sitc1 | fuel | maturity_bracket | flow
    industry: str | None = None  # SIC 2007 section for single-industry series
    group: str | None = None
    price_basis: str | None = None  # CVM | CP
    base_period: str | None = None
    decimals: int = 1
    params: dict = field(default_factory=dict)
    related: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    uncertainty: str = "The source does not publish a sampling error for this series through this endpoint."
    derived_from: tuple[str, ...] = ()
    formula: str | None = None
    enabled: bool = True
    max_lag_days: int | None = None  # overrides the frequency-based "delayed" heuristic for known long lags

    def to_dict(self) -> dict:
        return asdict(self)


def _ons(id, cdid, dataset, uri, title, category, definition, unit, measure_type, frequency, sa, **kw):
    params = {"cdid": cdid, "dataset": dataset, "uri": uri, **kw.pop("params", {})}
    return SeriesDef(
        id=id, source_id="ons", source_key=f"{cdid}/{dataset}", title=title, category=category,
        definition=definition, unit=unit, measure_type=measure_type, frequency=frequency,
        seasonal_adjustment=sa, params=params, **kw,
    )


ONS_REV = ("Subject to the ONS revisions policy; recent periods are routinely revised.",)

_series: list[SeriesDef] = [
    # ---------------------------------------------------------------- National accounts
    _ons("gdp_qoq", "IHYQ", "QNA", "/economy/grossdomesticproductgdp/timeseries/ihyq/qna",
         "GDP growth, quarter on quarter", "macro",
         "Percentage change in UK gross domestic product (chained volume measure, seasonally adjusted) "
         "compared with the previous quarter.", "%", "growth_rate", "Q", "SA", price_basis="CVM",
         related=("gdp_yoy", "gdp_level", "gdp_monthly_index", "hfce"), tags=("gdp", "growth"), notes=ONS_REV),
    _ons("gdp_yoy", "IHYR", "QNA", "/economy/grossdomesticproductgdp/timeseries/ihyr/qna",
         "GDP growth, year on year", "macro",
         "Percentage change in UK GDP (CVM, SA) compared with the same quarter a year earlier.",
         "%", "growth_rate", "Q", "SA", price_basis="CVM", related=("gdp_qoq", "gdp_level"), notes=ONS_REV),
    _ons("gdp_level", "ABMI", "QNA", "/economy/grossdomesticproductgdp/timeseries/abmi/qna",
         "GDP, chained volume measure", "macro",
         "UK gross domestic product at market prices, chained volume measure (reference-year prices), "
         "seasonally adjusted.", "£m", "level", "Q", "SA", price_basis="CVM", decimals=0,
         related=("gdp_qoq", "hfce"), notes=ONS_REV),
    _ons("gdp_monthly_index", "ECY2", "MGDP", "/economy/grossdomesticproductgdp/timeseries/ecy2/mgdp",
         "Monthly GDP (gross value added) index", "macro",
         "Monthly index of UK gross value added at basic prices, chained volume measure, seasonally adjusted.",
         "index", "index", "M", "SA", price_basis="CVM", related=("gdp_qoq", "iop_production", "ios_services"),
         notes=ONS_REV + ("Monthly GDP is volatile; ONS advises focusing on three-month-on-three-month growth.",)),
    _ons("hfce", "ABJR", "QNA", "/economy/nationalaccounts/satelliteaccounts/timeseries/abjr/qna",
         "Household final consumption expenditure", "macro",
         "Household final consumption expenditure, national concept, chained volume measure, SA.",
         "£m", "level", "Q", "SA", price_basis="CVM", decimals=0, related=("gdp_level", "retail_sales_volume"),
         notes=ONS_REV),
    _ons("productivity_oph", "LZVB", "PRDY",
         "/employmentandlabourmarket/peopleinwork/labourproductivity/timeseries/lzvb/prdy",
         "Labour productivity: output per hour", "macro",
         "UK whole-economy output per hour worked, seasonally adjusted index.", "index", "index", "Q", "SA",
         related=("gdp_level", "employment_rate"), notes=ONS_REV),
    _ons("retail_sales_volume", "J5EK", "DRSI", "/businessindustryandtrade/retailindustry/timeseries/j5ek/drsi",
         "Retail sales volume (incl. fuel)", "macro",
         "Retail sales index, chained volume, all retailers including automotive fuel, seasonally adjusted.",
         "index", "index", "M", "SA", price_basis="CVM", industry="G", related=("hfce", "cpi_yoy"), notes=ONS_REV),
    _ons("iop_production", "K222", "DIOP", "/economy/economicoutputandproductivity/output/timeseries/k222/diop",
         "Index of Production (B-E)", "industry",
         "Index of Production, sections B-E (production industries), CVM, seasonally adjusted.",
         "index", "index", "M", "SA", price_basis="CVM", related=("iop_manufacturing", "gdp_monthly_index"),
         notes=ONS_REV),
    _ons("iop_manufacturing", "K22A", "DIOP", "/economy/economicoutputandproductivity/output/timeseries/k22a/diop",
         "Manufacturing output (IoP section C)", "industry",
         "Index of Production, section C manufacturing, CVM, seasonally adjusted.", "index", "index", "M", "SA",
         industry="C", price_basis="CVM", related=("gva_C", "iop_production"), notes=ONS_REV),
    _ons("ios_services", "S2KU", "IOS1", "/economy/economicoutputandproductivity/output/timeseries/s2ku/ios1",
         "Index of Services", "industry", "Index of Services, total services, CVM, seasonally adjusted.",
         "index", "index", "M", "SA", price_basis="CVM", related=("gdp_monthly_index",), notes=ONS_REV),
    # ---------------------------------------------------------------- Prices
    _ons("cpi_yoy", "D7G7", "MM23", "/economy/inflationandpriceindices/timeseries/d7g7/mm23",
         "CPI inflation (12-month rate)", "prices",
         "Percentage change in the Consumer Prices Index (all items, 2015=100) over the previous 12 months.",
         "%", "growth_rate", "M", "NSA", group="cpi_headline",
         related=("cpih_yoy", "cpi_core_yoy", "cpi_index", "cpi_services_yoy", "cpi_goods_yoy", "bank_rate"),
         notes=("12-month rates are computed on non-seasonally-adjusted indices; seasonality largely cancels "
                "in the 12-month comparison. CPI is not normally revised.",)),
    _ons("cpih_yoy", "L55O", "MM23", "/economy/inflationandpriceindices/timeseries/l55o/mm23",
         "CPIH inflation (12-month rate)", "prices",
         "12-month percentage change in CPIH (CPI including owner occupiers' housing costs and council tax).",
         "%", "growth_rate", "M", "NSA", group="cpi_headline", related=("cpi_yoy",)),
    _ons("cpi_index", "D7BT", "MM23", "/economy/inflationandpriceindices/timeseries/d7bt/mm23",
         "CPI index, all items", "prices", "Consumer Prices Index, all items.", "index (2015=100)", "index",
         "M", "NSA", base_period="2015=100", related=("cpi_yoy",),
         notes=("Not seasonally adjusted: month-on-month changes include seasonal effects.",)),
    _ons("cpi_core_yoy", "DKO8", "MM23", "/economy/inflationandpriceindices/timeseries/dko8/mm23",
         "Core CPI inflation", "prices",
         "12-month rate of CPI excluding energy, food, alcoholic beverages and tobacco.",
         "%", "growth_rate", "M", "NSA", group="cpi_headline", related=("cpi_yoy", "cpi_services_yoy")),
    _ons("cpi_goods_yoy", "D7NM", "MM23", "/economy/inflationandpriceindices/timeseries/d7nm/mm23",
         "CPI goods inflation", "prices", "12-month rate of the CPI goods aggregate.", "%", "growth_rate", "M",
         "NSA", group="cpi_headline", related=("cpi_services_yoy",)),
    _ons("cpi_services_yoy", "D7NN", "MM23", "/economy/inflationandpriceindices/timeseries/d7nn/mm23",
         "CPI services inflation", "prices", "12-month rate of the CPI services aggregate.", "%", "growth_rate",
         "M", "NSA", group="cpi_headline", related=("cpi_goods_yoy", "awe_regular_growth")),
]

CPI_DIVISIONS = [
    ("01", "D7G8", "Food and non-alcoholic beverages"),
    ("02", "D7G9", "Alcoholic beverages and tobacco"),
    ("03", "D7GA", "Clothing and footwear"),
    ("04", "D7GB", "Housing, water, electricity, gas and other fuels"),
    ("05", "D7GC", "Furniture, household equipment and maintenance"),
    ("06", "D7GD", "Health"),
    ("07", "D7GE", "Transport"),
    ("08", "D7GF", "Communication"),
    ("09", "D7GG", "Recreation and culture"),
    ("10", "D7GH", "Education"),
    ("11", "D7GI", "Restaurants and hotels"),
    ("12", "D7GJ", "Miscellaneous goods and services"),
]
for code, cdid, name in CPI_DIVISIONS:
    _series.append(_ons(
        f"cpi_div_{code}", cdid, "MM23", f"/economy/inflationandpriceindices/timeseries/{cdid.lower()}/mm23",
        f"CPI {code}: {name}", "prices",
        f"12-month rate of the CPI COICOP division {code} ({name}). A published component of headline CPI.",
        "%", "growth_rate", "M", "NSA", group="cpi_divisions", params={"coicop": code},
        related=("cpi_yoy",), tags=("cpi", "component"),
    ))

_series += [
    # ---------------------------------------------------------------- Labour market
    _ons("unemployment_rate", "MGSX", "LMS",
         "/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms",
         "Unemployment rate (16+)", "labour",
         "ILO unemployment rate, people aged 16 and over, seasonally adjusted (Labour Force Survey, rolling "
         "three-month average).", "%", "rate", "M", "SA",
         related=("employment_rate", "inactivity_rate", "vacancies", "aps_unemployment_rate", "claimant_rate"),
         notes=("Periods are rolling three-month averages labelled by the final month.",
                "LFS response rates have fallen; ONS labels LFS estimates as 'official statistics in "
                "development' - treat month-to-month changes with caution."),
         uncertainty="LFS estimates carry sampling variability (ONS publishes ~95% CIs in its labour market "
                     "bulletin tables, not via this endpoint)."),
    _ons("employment_rate", "LF24", "LMS",
         "/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/timeseries/lf24/lms",
         "Employment rate (16-64)", "labour", "Employment rate, people aged 16 to 64, seasonally adjusted (LFS).",
         "%", "rate", "M", "SA", related=("unemployment_rate", "inactivity_rate")),
    _ons("inactivity_rate", "LF2S", "LMS",
         "/employmentandlabourmarket/peoplenotinwork/economicinactivity/timeseries/lf2s/lms",
         "Economic inactivity rate (16-64)", "labour",
         "Economic inactivity rate, people aged 16 to 64, seasonally adjusted (LFS).", "%", "rate", "M", "SA",
         related=("employment_rate",)),
    _ons("awe_total_growth", "KAC3", "LMS",
         "/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kac3/lms",
         "Pay growth: total pay (AWE)", "labour",
         "Average weekly earnings, whole economy, total pay excluding arrears: year-on-year growth of the "
         "three-month average, seasonally adjusted, nominal.", "%", "growth_rate", "M", "SA",
         related=("awe_regular_growth", "cpi_yoy")),
    _ons("awe_regular_growth", "KAI9", "LMS",
         "/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kai9/lms",
         "Pay growth: regular pay (AWE)", "labour",
         "Average weekly earnings, whole economy, regular pay excluding arrears: year-on-year growth of the "
         "three-month average, seasonally adjusted, nominal.", "%", "growth_rate", "M", "SA",
         related=("awe_total_growth", "cpi_services_yoy")),
    _ons("vacancies", "AP2Y", "LMS",
         "/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/timeseries/ap2y/lms",
         "Job vacancies", "labour", "UK job vacancies (thousands), rolling three-month average, SA.",
         "thousands", "level", "M", "SA", decimals=0, related=("unemployment_rate",)),
    # ---------------------------------------------------------------- Public finance
    _ons("psnb_ex", "J5II", "PUSF",
         "/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/j5ii/pusf",
         "Public sector net borrowing (ex. banks)", "public_finance",
         "Public sector net borrowing excluding public sector banks, current prices, not seasonally adjusted. "
         "Sign as published in series J5II: negative values denote net borrowing (a deficit).",
         "£m", "level", "M", "NSA", price_basis="CP", decimals=0, related=("psnd_ex", "psnd_ex_gdp"),
         notes=ONS_REV + ("Monthly borrowing is highly seasonal (self-assessment receipts in Jan/Jul); compare "
                          "with the same month a year earlier or use financial-year totals.",)),
    _ons("psnd_ex", "HF6W", "PUSF",
         "/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/hf6w/pusf",
         "Public sector net debt (ex. banks)", "public_finance",
         "Public sector net debt excluding public sector banks, £bn, current prices, NSA.", "£bn", "level",
         "M", "NSA", price_basis="CP", related=("psnd_ex_gdp", "gilts_in_issue"), notes=ONS_REV),
    _ons("psnd_ex_gdp", "HF6X", "PUSF",
         "/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/hf6x/pusf",
         "Public sector net debt, % of GDP", "public_finance",
         "Public sector net debt excluding public sector banks as a percentage of GDP (centred 12-month GDP).",
         "% of GDP", "share", "M", "NSA", related=("psnd_ex", "gilt_10y"), notes=ONS_REV),
    # ---------------------------------------------------------------- Trade (ONS, BoP basis)
    _ons("trade_balance", "IKBJ", "MRET", "/economy/nationalaccounts/balanceofpayments/timeseries/ikbj/mret",
         "Trade balance (goods and services)", "trade",
         "UK total trade balance (goods and services), worldwide, balance of payments basis, current prices, SA.",
         "£m", "level", "M", "SA", price_basis="CP", decimals=0, related=("exports_total", "imports_total"),
         notes=ONS_REV),
    _ons("exports_total", "IKBH", "MRET", "/economy/nationalaccounts/balanceofpayments/timeseries/ikbh/mret",
         "Exports (goods and services)", "trade", "UK total exports, BoP basis, current prices, SA.", "£m",
         "level", "M", "SA", price_basis="CP", decimals=0, related=("imports_total", "trade_balance")),
    _ons("imports_total", "IKBI", "MRET", "/economy/nationalaccounts/balanceofpayments/timeseries/ikbi/mret",
         "Imports (goods and services)", "trade", "UK total imports, BoP basis, current prices, SA.", "£m",
         "level", "M", "SA", price_basis="CP", decimals=0, related=("exports_total", "trade_balance")),
]

MGDP_SECTIONS = [
    ("A", "ECY3"), ("B", "ECY5"), ("C", "ECY6"), ("D", "ECY7"), ("E", "ECY8"), ("F", "ECY9"),
    ("G", "ECYD"), ("H", "ECYG"), ("I", "ECYH"), ("J", "ECYI"), ("K", "ECYJ"), ("L", "ECYK"),
    ("M", "ECYL"), ("N", "ECYP"), ("O", "ECYQ"), ("P", "ECYR"), ("Q", "ECYS"), ("R", "ECYT"), ("S", "ECYU"),
]
for sec, cdid in MGDP_SECTIONS:
    _series.append(_ons(
        f"gva_{sec}", cdid, "MGDP", f"/economy/grossdomesticproductgdp/timeseries/{cdid.lower()}/mgdp",
        f"Output: {SIC_SECTIONS[sec]}", "industry",
        f"Monthly gross value added index for SIC 2007 section {sec} ({SIC_SECTIONS[sec]}), chained volume "
        "measure, seasonally adjusted (monthly GDP release).",
        "index", "index", "M", "SA", industry=sec, group="gva_sections", price_basis="CVM",
        related=("gdp_monthly_index", "workforce_jobs", "business_counts"),
        tags=("industry", "sic2007"), notes=ONS_REV,
    ))

_series += [
    # ---------------------------------------------------------------- Bank of England
    SeriesDef("bank_rate", "boe", "IUDBEDR", "Bank Rate", "markets",
              "Official Bank Rate set by the Monetary Policy Committee (daily observation).", "%", "rate", "D",
              related=("sonia", "gilt_5y", "mortgage_2y_75", "cpi_yoy"),
              decimals=2, notes=("A policy rate: changes occur only at MPC decisions.",)),
    SeriesDef("sonia", "boe", "IUDSOIA", "SONIA", "markets",
              "Sterling Overnight Index Average, administered by the Bank of England.", "%", "rate", "D",
              decimals=4, related=("bank_rate",)),
    SeriesDef("gilt_5y", "boe", "IUDSNPY", "5-year gilt yield (nominal par)", "markets",
              "Bank of England estimate of the 5-year nominal par yield on UK government bonds (end of day).",
              "%", "rate", "D", decimals=3, related=("gilt_10y", "gilt_20y", "bank_rate")),
    SeriesDef("gilt_10y", "boe", "IUDMNPY", "10-year gilt yield (nominal par)", "markets",
              "Bank of England estimate of the 10-year nominal par yield on UK government bonds (end of day).",
              "%", "rate", "D", decimals=3, related=("gilt_5y", "gilt_20y", "psnd_ex_gdp")),
    SeriesDef("gilt_20y", "boe", "IUDLNPY", "20-year gilt yield (nominal par)", "markets",
              "Bank of England estimate of the 20-year nominal par yield on UK government bonds (end of day).",
              "%", "rate", "D", decimals=3, related=("gilt_10y",)),
    SeriesDef("mortgage_2y_75", "boe", "IUMBV34", "2-year fixed mortgage rate (75% LTV)", "markets",
              "Monthly quoted interest rate of UK MFIs on sterling 2-year fixed-rate mortgages at 75% "
              "loan-to-value, not seasonally adjusted.", "%", "rate", "M", "NSA", decimals=2,
              related=("mortgage_5y_75", "bank_rate", "mortgage_approvals", "hpi_avg_price")),
    SeriesDef("mortgage_5y_75", "boe", "IUMBV42", "5-year fixed mortgage rate (75% LTV)", "markets",
              "Monthly quoted interest rate of UK MFIs on sterling 5-year fixed-rate mortgages at 75% LTV, NSA.",
              "%", "rate", "M", "NSA", decimals=2, related=("mortgage_2y_75", "gilt_5y")),
    SeriesDef("mortgage_approvals", "boe", "LPMVTVX", "Mortgage approvals for house purchase", "housing",
              "Monthly number of total sterling approvals for house purchase to individuals, seasonally adjusted.",
              "number", "level", "M", "SA", decimals=0, related=("hpi_avg_price", "mortgage_2y_75")),
    SeriesDef("boe_gbp_usd", "boe", "XUDLUSS", "BoE spot: US$ into sterling", "markets",
              "Bank of England daily spot exchange rate, US$ per GBP.", "USD per GBP", "price", "D", decimals=4,
              enabled=False, notes=("Disabled by default: may contain third-party content with redistribution "
                                    "restrictions (see source caveats).",)),
    # ---------------------------------------------------------------- ECB FX
    SeriesDef("ecb_gbp_per_eur", "ecb", "D.GBP.EUR.SP00.A", "ECB reference rate: GBP per EUR", "markets",
              "Euro foreign exchange reference rate: pounds sterling per 1 euro, as published by the ECB.",
              "GBP per EUR", "price", "D", decimals=5, related=("fx_gbp_eur",)),
    SeriesDef("ecb_usd_per_eur", "ecb", "D.USD.EUR.SP00.A", "ECB reference rate: USD per EUR", "markets",
              "Euro foreign exchange reference rate: US dollars per 1 euro, as published by the ECB.",
              "USD per EUR", "price", "D", decimals=4),
    SeriesDef("ecb_jpy_per_eur", "ecb", "D.JPY.EUR.SP00.A", "ECB reference rate: JPY per EUR", "markets",
              "Euro foreign exchange reference rate: Japanese yen per 1 euro, as published by the ECB.",
              "JPY per EUR", "price", "D", decimals=2),
    SeriesDef("fx_gbp_eur", "ecb", "derived", "GBP/EUR (euros per pound)", "markets",
              "Euros per pound sterling, derived by this platform as the reciprocal of the ECB GBP-per-EUR "
              "reference rate.", "EUR per GBP", "price", "D", decimals=4, derived_from=("ecb_gbp_per_eur",),
              formula="1 / ecb_gbp_per_eur", related=("fx_gbp_usd", "bank_rate")),
    SeriesDef("fx_gbp_usd", "ecb", "derived", "GBP/USD (dollars per pound)", "markets",
              "US dollars per pound sterling, derived by this platform from ECB reference rates (cross rate).",
              "USD per GBP", "price", "D", decimals=4, derived_from=("ecb_usd_per_eur", "ecb_gbp_per_eur"),
              formula="ecb_usd_per_eur / ecb_gbp_per_eur", related=("fx_gbp_eur", "gilt_10y")),
    SeriesDef("fx_gbp_jpy", "ecb", "derived", "GBP/JPY (yen per pound)", "markets",
              "Japanese yen per pound sterling, derived by this platform from ECB reference rates (cross rate).",
              "JPY per GBP", "price", "D", decimals=2, derived_from=("ecb_jpy_per_eur", "ecb_gbp_per_eur"),
              formula="ecb_jpy_per_eur / ecb_gbp_per_eur"),
    # ---------------------------------------------------------------- NOMIS (regional)
    SeriesDef("aps_unemployment_rate", "nomis", "NM_17_5:83", "Unemployment rate (APS, regional)", "regional",
              "Annual Population Survey model-based unemployment rate, aged 16+, rolling 12 months ending in "
              "the period shown.", "%", "rate", "Q", "NSA", geography="itl1+nation+lad",
              params={"dataset": "NM_17_5", "variable": 83},
              related=("unemployment_rate", "claimant_rate", "aps_employment_rate"),
              uncertainty="NOMIS publishes a 95% confidence interval (+/- percentage points) for each estimate; "
                          "shown alongside each value.",
              notes=("Rolling 12-month averages - consecutive periods overlap by 9 months, so period-on-period "
                     "changes are not independent.",)),
    SeriesDef("aps_employment_rate", "nomis", "NM_17_5:45", "Employment rate 16-64 (APS, regional)", "regional",
              "Annual Population Survey employment rate, aged 16-64, rolling 12 months ending in the period shown.",
              "%", "rate", "Q", "NSA", geography="itl1+nation+lad", params={"dataset": "NM_17_5", "variable": 45},
              related=("employment_rate", "aps_unemployment_rate"),
              uncertainty="NOMIS publishes a 95% confidence interval for each estimate; shown alongside each value."),
    SeriesDef("claimant_rate", "nomis", "NM_162_1:2", "Claimant count rate", "regional",
              "Claimants (JSA and out-of-work Universal Credit) as a proportion of residents aged 16-64.",
              "%", "rate", "M", "NSA", geography="itl1+nation+lad", params={"dataset": "NM_162_1", "measure": 2},
              related=("claimant_count", "aps_unemployment_rate"),
              notes=("Not seasonally adjusted at local level. Affected by Universal Credit rollout; not ILO "
                     "unemployment.",)),
    SeriesDef("claimant_count", "nomis", "NM_162_1:1", "Claimant count", "regional",
              "Number of people claiming JSA or out-of-work Universal Credit.", "people", "level", "M", "NSA",
              geography="itl1+nation+lad", decimals=0, params={"dataset": "NM_162_1", "measure": 1},
              related=("claimant_rate",)),
    SeriesDef("ashe_weekly_pay_ft", "nomis", "NM_30_1", "Median weekly pay, full-time (residence)", "regional",
              "ASHE median gross weekly pay for full-time employees, by place of residence, nominal.", "£",
              "price", "A", geography="itl1+nation+lad", decimals=1, params={"dataset": "NM_30_1"},
              related=("awe_total_growth", "hpi_avg_price"),
              uncertainty="ASHE publishes a coefficient of variation (CV, %) per estimate; shown alongside each "
                          "value. ONS flags CV > 20% as unreliable.",
              notes=("Latest year is provisional and revised the following year.",)),
    SeriesDef("business_counts", "nomis", "NM_142_1", "Enterprises by industry (UK Business Counts)", "industry",
              "Count of VAT and/or PAYE registered enterprises by SIC 2007 section (IDBR), as at March.",
              "enterprises", "level", "A", geography="itl1+nation+lad", dim_kind="sic_section", decimals=0,
              params={"dataset": "NM_142_1"}, related=("workforce_jobs",),
              notes=("Counts are rounded by NOMIS (to nearest 5). Excludes small unregistered businesses.",
                     "Regional figures count enterprises by head-office location for multi-site firms.")),
    SeriesDef("workforce_jobs", "nomis", "NM_130_1", "Workforce jobs by industry", "industry",
              "Total workforce jobs (employee jobs, self-employment, HM Forces, trainees) by SIC 2007 section, "
              "seasonally adjusted.", "jobs", "level", "Q", "SA", geography="itl1+nation", dim_kind="sic_section",
              decimals=0, params={"dataset": "NM_130_1"}, related=("business_counts",)),
    # ---------------------------------------------------------------- Land Registry UK HPI
    SeriesDef("hpi_avg_price", "land_registry", "ukhpi:averagePrice", "Average house price (UK HPI)", "housing",
              "UK House Price Index average price (all property types), not seasonally adjusted.", "£", "price",
              "M", "NSA", geography="itl1+nation", decimals=0, params={"property": "averagePrice"},
              related=("hpi_yoy", "mortgage_approvals", "mortgage_2y_75", "ashe_weekly_pay_ft"),
              notes=("Recent months are revised as more transactions are registered.",)),
    SeriesDef("hpi_yoy", "land_registry", "ukhpi:percentageAnnualChange", "House price inflation (UK HPI)",
              "housing", "Annual percentage change in the UK HPI average price, as published.", "%", "growth_rate",
              "M", "NSA", geography="itl1+nation", params={"property": "percentageAnnualChange"},
              related=("hpi_avg_price", "cpi_yoy")),
    SeriesDef("hpi_index", "land_registry", "ukhpi:housePriceIndex", "House price index (UK HPI)", "housing",
              "UK House Price Index, all property types (Jan 2023 = 100), not seasonally adjusted.", "index",
              "index", "M", "NSA", geography="itl1+nation", base_period="Jan 2023=100",
              params={"property": "housePriceIndex"}, related=("hpi_avg_price",)),
    SeriesDef("hpi_sales_volume", "land_registry", "ukhpi:salesVolume", "Property sales volume (UK HPI)",
              "housing", "Number of sales used in the UK HPI for the month (lags; incomplete for recent months).",
              "sales", "level", "M", "NSA", geography="itl1+nation", decimals=0, max_lag_days=160,
              params={"property": "salesVolume"}, related=("mortgage_approvals",),
              notes=("Sales volumes for the latest ~2 months are incomplete and rise as registrations arrive.",)),
    # ---------------------------------------------------------------- HMRC OTS
    SeriesDef("hmrc_exports_partner", "hmrc_ots", "OTS:exports:country", "Goods exports by partner country",
              "trade", "HMRC Overseas Trade Statistics: value of UK goods exports by partner country (EU + "
              "non-EU flows).", "£", "level", "M", "NSA", dim_kind="partner_country", decimals=0,
              params={"flows": [2, 4], "by": "CountryId"}, related=("exports_total", "hmrc_imports_partner")),
    SeriesDef("hmrc_imports_partner", "hmrc_ots", "OTS:imports:country", "Goods imports by partner country",
              "trade", "HMRC Overseas Trade Statistics: value of UK goods imports by partner country.", "£",
              "level", "M", "NSA", dim_kind="partner_country", decimals=0,
              params={"flows": [1, 3], "by": "CountryId"}, related=("imports_total", "hmrc_exports_partner")),
    SeriesDef("hmrc_exports_sitc", "hmrc_ots", "OTS:exports:sitc1", "Goods exports by SITC section", "trade",
              "HMRC OTS: value of UK goods exports by SITC (Rev.4) section.", "£", "level", "M", "NSA",
              dim_kind="sitc1", decimals=0, params={"flows": [2, 4], "by": "CommoditySitcId"},
              related=("hmrc_imports_sitc",)),
    SeriesDef("hmrc_imports_sitc", "hmrc_ots", "OTS:imports:sitc1", "Goods imports by SITC section", "trade",
              "HMRC OTS: value of UK goods imports by SITC (Rev.4) section.", "£", "level", "M", "NSA",
              dim_kind="sitc1", decimals=0, params={"flows": [1, 3], "by": "CommoditySitcId"},
              related=("hmrc_exports_sitc", "cpi_div_04")),
    # ---------------------------------------------------------------- Energy
    SeriesDef("carbon_intensity", "neso_carbon", "intensity", "GB grid carbon intensity", "energy",
              "Estimated carbon intensity of GB electricity generation (actual where available, otherwise the "
              "NESO forecast), half-hourly.", "gCO2/kWh", "level", "HH", geography="gb", decimals=0,
              related=("generation_mix",), uncertainty="Modelled estimate; NESO publishes forecast and 'actual' "
                                                         "(estimated) values. Flags record which is shown."),
    SeriesDef("generation_mix", "neso_carbon", "generation", "GB generation mix", "energy",
              "Share of GB electricity generation by fuel type, half-hourly.", "% of generation", "share", "HH",
              geography="gb", dim_kind="fuel", related=("carbon_intensity", "gva_D")),
    SeriesDef("fuel_petrol", "desnz_fuel", "ULSP", "Unleaded petrol pump price", "energy",
              "UK average pump price of ultra-low-sulphur unleaded petrol (weekly, including duty and VAT).",
              "pence per litre", "price", "W", decimals=2, related=("fuel_diesel", "cpi_div_07")),
    SeriesDef("fuel_diesel", "desnz_fuel", "ULSD", "Diesel pump price", "energy",
              "UK average pump price of ultra-low-sulphur diesel (weekly, including duty and VAT).",
              "pence per litre", "price", "W", decimals=2, related=("fuel_petrol", "cpi_div_07")),
    # ---------------------------------------------------------------- DMO
    SeriesDef("gilts_in_issue", "dmo", "D1A", "Gilts in issue by maturity bracket", "public_finance",
              "Nominal amount of gilts in issue (GBP m, excluding index-linked uplift), summed by DMO maturity "
              "bracket and instrument type at close of business.", "£m nominal", "level", "D",
              dim_kind="maturity_bracket", decimals=0, related=("psnd_ex", "gilt_10y")),
]

CATALOGUE: dict[str, SeriesDef] = {s.id: s for s in _series}


def series_for_source(source_id: str) -> list[SeriesDef]:
    return [s for s in CATALOGUE.values() if s.source_id == source_id]
