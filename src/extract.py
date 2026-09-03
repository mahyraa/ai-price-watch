"""Turn a page of pricing text into structured model records.

This is the design decision the whole project rests on.

The obvious way to build a change watcher is to hash the page HTML and alert
when the hash moves. That does not work here: pricing pages are rebuilt
constantly, so you get a "change" every single run from a rotated CSS hash or a
reordered nav, and none of them are about pricing. Signal-to-noise ~0.

Instead we extract a normalized record per model (name, input price, output
price, context window) and diff THAT. A page can be redesigned end to end and
produce zero changes, which is correct — the pricing didn't change.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

import anthropic

# The schema we ask the model to fill in. Anthropic's tool-use mode constrains
# output to this shape, which is far more reliable than "reply with JSON".
PRICING_TOOL = {
    "name": "record_pricing",
    "description": "Record the per-model API pricing found on the page.",
    "input_schema": {
        "type": "object",
        "properties": {
            "models": {
                "type": "array",
                "description": (
                    "One entry per model with published API pricing. Skip "
                    "subscription plans (Pro/Team/Enterprise seats), free tiers, "
                    "and anything without a token price."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Model name exactly as written on the page.",
                        },
                        "input_per_mtok": {
                            "type": ["number", "null"],
                            "description": (
                                "USD per 1M input tokens. Convert if the page "
                                "quotes per 1K. Use the standard/base tier if "
                                "several are listed. Null if not published."
                            ),
                        },
                        "output_per_mtok": {
                            "type": ["number", "null"],
                            "description": "USD per 1M output tokens, same rules.",
                        },
                        "context_window": {
                            "type": ["integer", "null"],
                            "description": "Context window in tokens, if stated.",
                        },
                        "notes": {
                            "type": "string",
                            "description": (
                                "Short caveat if pricing is tiered, promotional, "
                                "or time-limited. Empty string if none."
                            ),
                        },
                    },
                    "required": ["name", "input_per_mtok", "output_per_mtok", "notes"],
                },
            }
        },
        "required": ["models"],
    },
}

PROMPT = """Below is the visible text of {provider}'s public API pricing page.

Extract every model that has published per-token API pricing and record it with
the record_pricing tool.

Rules:
- Be exhaustive and consistent: record EVERY row in every pricing table,
  including older, legacy, and deprecated models. Do not summarise, sample, or
  omit rows you consider unimportant. The same page must always produce the same
  list.
- Use the model name exactly as printed, without reformatting or expanding it.
- Prices are USD per 1 million tokens. If the page quotes per 1,000 tokens,
  multiply by 1000.
- If a model has tiered pricing (e.g. a different rate above 200k tokens), use
  the base/standard rate and describe the tiering in `notes`.
- Ignore seat-based subscription plans, free tiers, and fine-tuning/storage
  line items. Only per-token inference pricing.
- One entry per model. If a model appears in several tables, record it once.
- MODALITY: some models publish separate rates for text, audio, and image
  tokens. ALWAYS use the TEXT rate as input_per_mtok/output_per_mtok, and list
  the other modalities in `notes`. If a model has no text rate, use its cheapest
  published rate and say which modality it is in `notes`. Picking a different
  modality between runs is the main source of false price changes, so this rule
  is not optional.
- If the page has no per-token pricing at all, return an empty list.

PAGE TEXT:
{text}
"""


@dataclass(frozen=True)
class ModelPrice:
    name: str
    input_per_mtok: float | None
    output_per_mtok: float | None
    context_window: int | None = None
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ExtractionError(Exception):
    pass


def _client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ExtractionError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add "
            "your key, or set it as a GitHub Actions secret."
        )
    return anthropic.Anthropic(api_key=key)


def extract_models(page_text: str, provider: str, model: str) -> list[ModelPrice]:
    """Ask the LLM to pull structured pricing out of page text."""
    client = _client()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        tools=[PRICING_TOOL],
        tool_choice={"type": "tool", "name": "record_pricing"},
        messages=[
            {
                "role": "user",
                "content": PROMPT.format(provider=provider, text=page_text),
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use":
            return _parse(block.input)

    raise ExtractionError(f"{provider}: model did not call the extraction tool")


def _parse(payload: dict) -> list[ModelPrice]:
    models: list[ModelPrice] = []
    for row in payload.get("models", []):
        name = (row.get("name") or "").strip()
        if not name:
            continue
        models.append(
            ModelPrice(
                name=name,
                input_per_mtok=_num(row.get("input_per_mtok")),
                output_per_mtok=_num(row.get("output_per_mtok")),
                context_window=_int(row.get("context_window")),
                notes=(row.get("notes") or "").strip(),
            )
        )
    return models


def _num(value) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def dump_models(models: list[ModelPrice]) -> str:
    return json.dumps([m.to_dict() for m in models], indent=2, sort_keys=True)
