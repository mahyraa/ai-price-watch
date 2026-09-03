"""Orchestrates one run: fetch -> extract -> diff -> record -> render.

Usage:
    python -m src.run                 # all sources
    python -m src.run --only openai   # one source, for debugging
    python -m src.run --no-site       # skip site generation
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from .config import SITE_DIR, SNAPSHOT_DIR, Config, Source
from .diff import diff_snapshots
from .extract import ExtractionError, extract_models
from .fetch import FetchError, fetch_text
from .render import load_json, render_site
from .summarize import write_digest

HISTORY_PATH = SNAPSHOT_DIR.parent / "history.json"


def run(only: str | None = None, build_site: bool = True) -> int:
    config = Config.load()
    sources = [s for s in config.sources if not only or s.key == only]
    if not sources:
        print(f"no source matching '{only}'", file=sys.stderr)
        return 2

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    snapshots: dict[str, dict] = {}
    all_changes = []
    broken: list[str] = []

    for source in sources:
        previous = load_json(_snapshot_path(source.key), None)
        result = _process(source, config, previous)

        if result["status"] == "broken":
            broken.append(source.name)
            print(f"  ! {source.key}: {result['reason']}")
            # Keep serving the last good data rather than blanking the provider.
            if previous:
                snapshots[source.key] = previous
            continue

        snapshots[source.key] = result["snapshot"]
        changes = result["changes"]
        all_changes.extend(changes)

        summary = f"{len(result['snapshot']['models'])} models"
        if changes:
            summary += f", {len(changes)} change(s)"
        print(f"  · {source.key}: {summary}")
        for change in changes:
            print(f"      [{change.severity}] {change.describe()}")

    # Load every stored snapshot so a --only run still renders a full site.
    if build_site:
        for source in config.sources:
            if source.key not in snapshots:
                stored = load_json(_snapshot_path(source.key), None)
                if stored:
                    snapshots[source.key] = stored

    digest = write_digest(all_changes, config.summarize_model)

    history = load_json(HISTORY_PATH, [])
    history.append(
        {
            "date": date.today().isoformat(),
            "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "digest": digest,
            "broken": broken,
            "changes": [
                {**c.to_dict(), "text": c.describe()} for c in all_changes
            ],
        }
    )
    HISTORY_PATH.write_text(json.dumps(history, indent=2))

    if build_site:
        index = render_site(
            snapshots=snapshots,
            history=history,
            digest=digest,
            broken=broken,
            out_dir=SITE_DIR,
        )
        print(f"\nsite -> {index}")

    print(f"\n{'-' * 60}\n{digest}\n{'-' * 60}")
    if broken:
        print(f"\nsources needing attention: {', '.join(broken)}")

    return 0


def _process(source: Source, config: Config, previous: dict | None) -> dict:
    try:
        page_text = fetch_text(source.url)
    except FetchError as exc:
        return {"status": "broken", "reason": str(exc)}

    try:
        models = extract_models(page_text, source.name, config.extract_model)
    except ExtractionError as exc:
        return {"status": "broken", "reason": str(exc)}
    except Exception as exc:  # noqa: BLE001
        # An API hiccup on one provider shouldn't abort the other nine.
        return {"status": "broken", "reason": f"{type(exc).__name__}: {exc}"}

    # The guard that matters: a scraper that quietly starts returning nothing is
    # worse than one that crashes, because it reports "no changes" forever.
    if len(models) < source.expect_min:
        return {
            "status": "broken",
            "reason": (
                f"extracted {len(models)} models, expected at least "
                f"{source.expect_min} — page structure probably changed"
            ),
        }

    snapshot = {
        "provider": source.key,
        "provider_name": source.name,
        "source_url": source.url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "models": [m.to_dict() for m in models],
    }

    changes = []
    if previous:
        changes = diff_snapshots(
            source.name,
            previous.get("models", []),
            snapshot["models"],
            major_price_move=config.major_price_move,
        )

    _snapshot_path(source.key).write_text(json.dumps(snapshot, indent=2, sort_keys=True))
    return {"status": "ok", "snapshot": snapshot, "changes": changes}


def _snapshot_path(key: str) -> Path:
    return SNAPSHOT_DIR / f"{key}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AI pricing watcher.")
    parser.add_argument("--only", help="run a single source by key")
    parser.add_argument("--no-site", action="store_true", help="skip site generation")
    args = parser.parse_args()
    print(f"AI Price Watch — run {date.today().isoformat()}\n")
    return run(only=args.only, build_site=not args.no_site)


if __name__ == "__main__":
    raise SystemExit(main())
