"""Probe suites, each a self-contained argument against observed behaviour."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..client import Moss
from ..model import ProbeResult


@dataclass(frozen=True)
class Probe:
    id: str
    title: str
    fn: Callable[[Moss, object], ProbeResult]


from . import (  # noqa: E402
    contract,
    failures,
    files,
    idempotency,
    inference,
    lifecycle,
    listing,
    money,
    schema,
    sdk,
    surface,
)

SUITES: dict[str, list[Probe]] = {
    "surface": [Probe("P", "Unauthenticated surface", surface.run)],
    "listing": [Probe("R", "The undocumented list route", listing.run)],
    "inference": [Probe("N", "Inference path and the indexes header", inference.run)],
    "contract": [Probe("C", "Request validation and error shape", contract.run)],
    "idempotency": [Probe("I", "Idempotency-Key semantics", idempotency.run)],
    "lifecycle": [Probe("L", "Task state machine and cancellation", lifecycle.run)],
    "money": [Probe("M", "Cost accounting and budget failure", money.run)],
    "schema": [Probe("V", "output_schema and verification", schema.run)],
    "failures": [Probe("F", "Failure taxonomy", failures.run)],
    "files": [Probe("G", "Task files", files.run)],
    "sdk": [Probe("D", "SDK polling behaviour", sdk.run)],
}
