"""Companies House Public Data API (on demand; requires a free API key)."""
from __future__ import annotations

import re

from ..config import get_settings
from .base import Connector, FetchResult, SourceError

API = "https://api.company-information.service.gov.uk"
WEB = "https://find-and-update.company-information.service.gov.uk/company/{n}"

PROFILE_FIELDS = ("company_name", "company_number", "company_status", "company_status_detail", "type",
                  "date_of_creation", "date_of_cessation", "jurisdiction", "sic_codes", "registered_office_address",
                  "accounts", "confirmation_statement", "has_charges", "has_insolvency_history", "can_file")


class CompaniesHouseConnector(Connector):
    source_id = "companies_house"

    def _auth(self) -> tuple[str, str]:
        key = get_settings().companies_house_api_key
        if not key:
            raise SourceError("Companies House API key not configured (free registration required)", kind="disabled")
        return (key, "")  # HTTP basic: key as username, blank password

    def search(self, q: str, limit: int = 20) -> dict:
        q = q.strip()
        if not q or len(q) > 100:
            raise SourceError("Invalid query", kind="validation")
        r = self.http.get(f"{API}/search/companies", params={"q": q, "items_per_page": min(limit, 50)},
                          auth=self._auth(), cache_ttl_s=3600)
        js = r.json()
        items = [{
            "company_number": i.get("company_number"), "title": i.get("title"),
            "company_status": i.get("company_status"), "company_type": i.get("company_type"),
            "date_of_creation": i.get("date_of_creation"), "address_snippet": i.get("address_snippet"),
        } for i in js.get("items", [])]
        return {"request_url": r.url, "total_results": js.get("total_results"), "items": items,
                "retrieved_at": r.fetched_at.isoformat(), "from_cache": r.from_cache}

    def profile(self, number: str) -> dict:
        if not re.fullmatch(r"[A-Z0-9]{8}", number.upper()):
            raise SourceError("Company number must be 8 characters", kind="validation")
        number = number.upper()
        r = self.http.get(f"{API}/company/{number}", auth=self._auth(), cache_ttl_s=3600 * 6)
        js = r.json()
        prof = {k: js.get(k) for k in PROFILE_FIELDS if k in js}
        fh = self.http.get(f"{API}/company/{number}/filing-history", params={"items_per_page": 25},
                           auth=self._auth(), cache_ttl_s=3600 * 6)
        filings = [{"date": f.get("date"), "category": f.get("category"), "type": f.get("type"),
                    "description": f.get("description"), "transaction_id": f.get("transaction_id")}
                   for f in fh.json().get("items", [])]
        return {"profile": prof, "filings": filings, "request_urls": [r.url, fh.url], "web_url": WEB.format(n=number),
                "retrieved_at": r.fetched_at.isoformat()}

    def fetch(self, series_ids=None) -> FetchResult:  # on-demand source, nothing scheduled
        return FetchResult()
