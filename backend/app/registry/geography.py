"""Reference geography: UK, nations and ITL1 regions with their codes in each source.

ITL 2025 codes (TLC..TLN) come from the ONS ITL1_JAN_2025 boundary layer; GSS region/country codes
(E12000001.., W92000004, S92000003, N92000002) are what NOMIS returns; Land Registry uses URI slugs
(verified via SPARQL on 2026-10-26 - note the region is 'west-midlands-region', 'west-midlands' is the
metropolitan county). Local authorities are loaded from the ONS LAD25 -> ITL lookup at runtime.
"""
from __future__ import annotations

UK_CODE = "K02000001"
GB_CODE = "K03000001"

# (gss, name, level, parent, itl1, land_registry_slug)
AREAS: list[tuple[str, str, str, str | None, str | None, str | None]] = [
    (UK_CODE, "United Kingdom", "uk", None, None, "united-kingdom"),
    (GB_CODE, "Great Britain", "gb", UK_CODE, None, "great-britain"),
    ("E92000001", "England", "nation", UK_CODE, None, "england"),
    ("W92000004", "Wales", "nation", UK_CODE, "TLL", "wales"),
    ("S92000003", "Scotland", "nation", UK_CODE, "TLM", "scotland"),
    ("N92000002", "Northern Ireland", "nation", UK_CODE, "TLN", "northern-ireland"),
    ("E12000001", "North East", "itl1", "E92000001", "TLC", "north-east"),
    ("E12000002", "North West", "itl1", "E92000001", "TLD", "north-west"),
    ("E12000003", "Yorkshire and The Humber", "itl1", "E92000001", "TLE", "yorkshire-and-the-humber"),
    ("E12000004", "East Midlands", "itl1", "E92000001", "TLF", "east-midlands"),
    ("E12000005", "West Midlands", "itl1", "E92000001", "TLG", "west-midlands-region"),
    ("E12000006", "East of England", "itl1", "E92000001", "TLH", "east-of-england"),
    ("E12000007", "London", "itl1", "E92000001", "TLI", "london"),
    ("E12000008", "South East", "itl1", "E92000001", "TLJ", "south-east"),
    ("E12000009", "South West", "itl1", "E92000001", "TLK", "south-west"),
]

ITL_TO_GSS = {a[4]: a[0] for a in AREAS if a[4]}
GSS_TO_ITL = {v: k for k, v in ITL_TO_GSS.items()}
LR_SLUG_TO_GSS = {a[5]: a[0] for a in AREAS if a[5]}
NAMES = {a[0]: a[1] for a in AREAS}

# The 12 map regions at ITL1 level (Wales/Scotland/NI are both nations and ITL1 regions).
ITL1_GSS = [g for g, _, lvl, _, itl, _ in AREAS if itl is not None]
