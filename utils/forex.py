"""Fetch PHP → foreign rates (Frankfurter API, no API key)."""

from __future__ import annotations

from typing import Any

import aiohttp

FRANKFURTER = "https://api.frankfurter.app/latest"


async def fetch_php_rates(
    targets: list[str],
) -> dict[str, float] | None:
    """
    Returns map currency_code -> amount of that currency per 1 PHP.
    Frankfurter returns rates with base PHP: rates[USD] = USD per 1 PHP.
    """
    if not targets:
        return {}
    t = sorted({x.upper().strip() for x in targets if x})
    if not t:
        return {}
    params = {"from": "PHP", "to": ",".join(t)}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FRANKFURTER, params=params, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status != 200:
                    return None
                data: dict[str, Any] = await resp.json()
    except (aiohttp.ClientError, TimeoutError):
        return None
    rates = data.get("rates") or {}
    out: dict[str, float] = {}
    for code in t:
        v = rates.get(code)
        if isinstance(v, (int, float)):
            out[code] = float(v)
    return out if out else None
