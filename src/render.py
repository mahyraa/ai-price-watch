"""Render the public site from the stored snapshots and change history."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

AUTHOR = "Mahyra Afif"
AUTHOR_URL = "https://www.linkedin.com/in/mahyra-afif"
REPO_URL = "https://github.com/mahyraa/ai-price-watch"


def render_site(
    *,
    snapshots: dict[str, dict],
    history: list[dict],
    digest: str,
    broken: list[str],
    out_dir: Path,
) -> Path:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("index.html.jinja")

    pricing_rows = _pricing_rows(snapshots)
    html = template.render(
        providers=sorted(snapshots.keys()),
        pricing_rows=pricing_rows,
        model_count=len(pricing_rows),
        run_count=len(history),
        digest_paragraphs=[p.strip() for p in digest.split("\n") if p.strip()],
        archive=_archive(history),
        broken=broken,
        generated_at=datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC"),
        author=AUTHOR,
        author_url=AUTHOR_URL,
        repo_url=REPO_URL,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    # .nojekyll stops GitHub Pages from running Jekyll over the output.
    (out_dir / ".nojekyll").write_text("")
    index = out_dir / "index.html"
    index.write_text(html)
    return index


def _pricing_rows(snapshots: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for key in sorted(snapshots):
        snapshot = snapshots[key]
        provider = snapshot.get("provider_name", key)
        for model in snapshot.get("models", []):
            rows.append(
                {
                    "provider": provider,
                    "name": model.get("name", ""),
                    "notes": model.get("notes", ""),
                    "input": _money(model.get("input_per_mtok")),
                    "output": _money(model.get("output_per_mtok")),
                    "context": _tokens(model.get("context_window")),
                }
            )
    return rows


def _archive(history: list[dict], limit: int = 40) -> list[dict]:
    entries = []
    for run in reversed(history[-limit:]):
        if not run.get("changes"):
            continue
        entries.append(
            {
                "date": run.get("date", ""),
                "changes": [
                    {
                        "severity": c.get("severity", "minor"),
                        "text": c.get("text", ""),
                        "direction": _direction(c),
                    }
                    for c in run["changes"]
                ],
            }
        )
    return entries


def _direction(change: dict) -> str:
    pct = change.get("pct")
    if pct is None:
        return ""
    return "down" if pct < 0 else "up"


def _money(value) -> str:
    if value is None:
        return "—"
    if float(value).is_integer():
        return f"${int(value)}"
    return f"${value:g}"


def _tokens(value) -> str:
    if not value:
        return "—"
    if value >= 1_000_000:
        return f"{value / 1_000_000:g}M"
    if value >= 1_000:
        return f"{value // 1000}K"
    return str(value)


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default
