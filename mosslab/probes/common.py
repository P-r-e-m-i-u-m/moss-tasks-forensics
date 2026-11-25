"""Shared payloads. Kept small on purpose: every task here is paid for."""

from __future__ import annotations

from typing import Any

# A page that is boring, fast, and stable. Any failure here is the API's, not the web's.
START = "https://example.com"


def task(**overrides: Any) -> dict[str, Any]:
    """A minimal valid task body. Overrides replace top-level keys."""
    payload: dict[str, Any] = {
        "goal": "Open the page and report its title.",
        "environment": {"type": "browser", "start_url": START},
        "model": "moss-fast",
        "limits": {"max_runtime_seconds": 90, "max_cost_usd": 0.02},
    }
    payload.update(overrides)
    return payload


def slow_task(**overrides: Any) -> dict[str, Any]:
    """A goal that cannot plausibly finish in a minute, for limit tests."""
    payload = task(
        goal=(
            "Open https://en.wikipedia.org/wiki/List_of_countries_by_population_(United_Nations). "
            "For each of the first twenty countries in the table, open its article and record "
            "the population figure and the year it was reported. Then summarise the ten largest."
        ),
        limits={"max_runtime_seconds": 120, "max_cost_usd": 0.05},
    )
    payload.update(overrides)
    return payload
