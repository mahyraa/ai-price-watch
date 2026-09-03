"""Write the human-facing digest for a run's changes.

The diff engine already decided WHAT changed and how much it mattered. This step
only writes it up — it is explicitly told not to invent significance the data
doesn't support, because the failure mode of an LLM digest is breathless prose
about a rounding error.
"""

from __future__ import annotations

import os

import anthropic

from .diff import Change

SYSTEM = """You write a short weekly digest of AI model pricing changes for \
people who build on these APIs.

Style rules:
- Lead with the change that most affects someone's bill.
- Plain, specific, unexcited. No hype words, no "game-changing", no emoji.
- Quote the actual numbers. Never invent a number that isn't in the input.
- If a change is small, say it's small. Do not manufacture significance.
- 120 words maximum. No headings. Two short paragraphs at most.
- If you genuinely cannot tell why a change matters, describe it and stop."""

PROMPT = """Changes detected this run:

{changes}

Write the digest."""

NO_CHANGES = (
    "No pricing changes detected across the tracked providers this run."
)


def write_digest(changes: list[Change], model: str) -> str:
    if not changes:
        return NO_CHANGES

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        # Degrade to the mechanical description rather than failing the run.
        return "\n".join(f"- {c.describe()}" for c in changes)

    lines = []
    for change in changes:
        marker = "[major]" if change.severity == "major" else "[minor]"
        lines.append(f"{marker} {change.describe()}")

    client = anthropic.Anthropic(api_key=key)
    response = client.messages.create(
        model=model,
        max_tokens=600,
        system=SYSTEM,
        messages=[{"role": "user", "content": PROMPT.format(changes="\n".join(lines))}],
    )

    parts = [b.text for b in response.content if b.type == "text"]
    return "\n".join(parts).strip() or NO_CHANGES
