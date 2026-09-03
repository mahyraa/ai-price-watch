"""Compare two snapshots of a provider's pricing and classify what moved.

Pure functions, no network and no API calls, which is why this is the part with
real unit tests. Everything else in the pipeline is plumbing around it.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

ADDED = "model_added"
REMOVED = "model_removed"
PRICE = "price_changed"
CONTEXT = "context_changed"

MAJOR = "major"
MINOR = "minor"


@dataclass(frozen=True)
class Change:
    provider: str
    kind: str
    model: str
    field: str = ""
    old: float | int | None = None
    new: float | int | None = None
    pct: float | None = None
    severity: str = MINOR

    def to_dict(self) -> dict:
        return asdict(self)

    def describe(self) -> str:
        if self.kind == ADDED:
            return f"{self.provider}: new model {self.model}"
        if self.kind == REMOVED:
            return f"{self.provider}: {self.model} removed from pricing page"
        if self.kind == CONTEXT:
            return (
                f"{self.provider}: {self.model} context window "
                f"{_fmt(self.old)} -> {_fmt(self.new)}"
            )
        # pct is undefined when a price appears from nothing, disappears, or the
        # previous price was zero — so the percentage is optional here.
        if self.pct is None:
            if self.old is None:
                return f"{self.provider}: {self.model} {self.field} price published at ${_fmt(self.new)}"
            if self.new is None:
                return f"{self.provider}: {self.model} {self.field} price no longer published"
            direction = "cut" if self.new < self.old else "raised"
            return (
                f"{self.provider}: {self.model} {self.field} price {direction} "
                f"${_fmt(self.old)} -> ${_fmt(self.new)}"
            )
        direction = "cut" if self.pct < 0 else "raised"
        return (
            f"{self.provider}: {self.model} {self.field} price {direction} "
            f"${_fmt(self.old)} -> ${_fmt(self.new)} ({self.pct:+.0%})"
        )


def normalize(name: str) -> str:
    """Collapse a model name to a stable matching key.

    'Claude Sonnet 5', 'claude-sonnet-5' and 'Claude  Sonnet  5 ' all become
    'claudesonnet5'. Without this, cosmetic renames on the page read as a
    removal plus an addition every time.
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


def diff_snapshots(
    provider: str,
    old_models: list[dict],
    new_models: list[dict],
    *,
    major_price_move: float = 0.05,
) -> list[Change]:
    """Return the changes between two lists of model records."""
    old_by_key = {normalize(m["name"]): m for m in old_models}
    new_by_key = {normalize(m["name"]): m for m in new_models}

    changes: list[Change] = []

    for key, model in new_by_key.items():
        if key not in old_by_key:
            changes.append(
                Change(
                    provider=provider,
                    kind=ADDED,
                    model=model["name"],
                    severity=MAJOR,
                )
            )

    for key, model in old_by_key.items():
        if key not in new_by_key:
            changes.append(
                Change(
                    provider=provider,
                    kind=REMOVED,
                    model=model["name"],
                    severity=MAJOR,
                )
            )

    for key in old_by_key.keys() & new_by_key.keys():
        old, new = old_by_key[key], new_by_key[key]
        for field in ("input_per_mtok", "output_per_mtok"):
            changes.extend(
                _price_change(provider, new["name"], field, old, new, major_price_move)
            )
        changes.extend(_context_change(provider, new["name"], old, new))

    changes.sort(key=lambda c: (c.severity != MAJOR, c.model, c.field))
    return changes


def _price_change(
    provider: str,
    name: str,
    field: str,
    old: dict,
    new: dict,
    major_price_move: float,
) -> list[Change]:
    old_value, new_value = old.get(field), new.get(field)

    # A price appearing or disappearing is worth reporting, but percentage
    # change is undefined, so it is treated as major on its own.
    if old_value is None or new_value is None:
        if old_value != new_value:
            return [
                Change(
                    provider=provider,
                    kind=PRICE,
                    model=name,
                    field=_label(field),
                    old=old_value,
                    new=new_value,
                    severity=MAJOR,
                )
            ]
        return []

    if old_value == new_value:
        return []

    pct = (new_value - old_value) / old_value if old_value else None
    severity = (
        MAJOR if pct is None or abs(pct) >= major_price_move else MINOR
    )
    return [
        Change(
            provider=provider,
            kind=PRICE,
            model=name,
            field=_label(field),
            old=old_value,
            new=new_value,
            pct=pct,
            severity=severity,
        )
    ]


def _context_change(provider: str, name: str, old: dict, new: dict) -> list[Change]:
    old_value, new_value = old.get("context_window"), new.get("context_window")
    if old_value == new_value or old_value is None or new_value is None:
        return []
    return [
        Change(
            provider=provider,
            kind=CONTEXT,
            model=name,
            field="context window",
            old=old_value,
            new=new_value,
            severity=MAJOR,
        )
    ]


def _label(field: str) -> str:
    return {"input_per_mtok": "input", "output_per_mtok": "output"}.get(field, field)


def _fmt(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int) or float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:g}"
