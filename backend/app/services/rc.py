"""Vehicle registration (RC) lookup behind a provider interface.

The v1 app scraped vahanx.in directly; v2 isolates it behind a protocol so the
scraper can be swapped for an official/aggregator API without touching callers.
Disabled by default via GeneralSettings.rc_lookup_enabled.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx
from bs4 import BeautifulSoup

from app.models import RcCache

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 24
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class RcProvider(Protocol):
    name: str

    async def fetch(self, clean_vrn: str) -> dict | None: ...


class NullProvider:
    name = "none"

    async def fetch(self, clean_vrn: str) -> dict | None:
        return None


class VahanxScraper:
    name = "vahanx.in"

    async def fetch(self, clean_vrn: str) -> dict | None:
        url = f"https://vahanx.in/rc-search/{clean_vrn}"
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": UA})
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.content, "html.parser")
        if not soup.find("h3", string="Ownership Details"):
            return None
        details: dict[str, str] = {}
        header_card = soup.find("div", class_="hrc-details-card")
        if header_card:
            for label_text in ("Code", "City Name"):
                el = header_card.find("span", string=label_text)
                if el and el.find_previous_sibling("p"):
                    details[label_text] = el.find_previous_sibling("p").get_text(strip=True)
        for heading in ("Ownership Details", "Vehicle Details"):
            section = soup.find("h3", string=heading)
            if not section:
                continue
            card = section.find_parent("div", class_="hrc-details-card")
            if not card:
                continue
            for item in card.find_all("div", class_="col-sm-6"):
                label = item.find("span", class_="text-muted")
                value = item.find("p", class_="fw-semibold")
                if label and value:
                    details[label.get_text(strip=True)] = value.get_text(strip=True)
        return {"source": self.name, "details": details, "model": details.get("Maker Model", "")}


_provider: RcProvider = VahanxScraper()


def get_provider() -> RcProvider:
    return _provider


def set_provider(provider: RcProvider) -> None:
    global _provider
    _provider = provider


async def lookup_rc(db, vrn_normalized: str) -> dict:
    provider = get_provider()
    cached = await db.get(RcCache, vrn_normalized)
    if cached:
        fetched = cached.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=UTC)
        if datetime.now(UTC) - fetched < timedelta(hours=CACHE_TTL_HOURS):
            return {"status": "ok", "source": cached.source, "cached": True, "payload": cached.payload}
    result = await provider.fetch(vrn_normalized)
    if not result or not result.get("details"):
        return {"status": "not_found", "message": "no RC details available"}
    payload = result["details"]
    db.add(RcCache(vrn_normalized=vrn_normalized, payload=payload, source=result.get("source", "")))
    await db.commit()
    return {"status": "ok", "source": result.get("source", provider.name), "cached": False, "payload": payload}
