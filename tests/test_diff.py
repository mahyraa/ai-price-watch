"""Tests for the diff engine — the part that decides what counts as news."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.diff import (  # noqa: E402
    ADDED,
    CONTEXT,
    MAJOR,
    MINOR,
    PRICE,
    REMOVED,
    diff_snapshots,
    normalize,
)


def model(name, inp=1.0, out=5.0, ctx=None, notes=""):
    return {
        "name": name,
        "input_per_mtok": inp,
        "output_per_mtok": out,
        "context_window": ctx,
        "notes": notes,
    }


def test_identical_snapshots_produce_no_changes():
    snapshot = [model("Sonnet 5"), model("Haiku 4.5", 0.8, 4.0)]
    assert diff_snapshots("anthropic", snapshot, snapshot) == []


def test_page_redesign_with_same_prices_produces_no_changes():
    """The whole point of extracting structure instead of diffing HTML."""
    old = [model("Claude Sonnet 5", 2.0, 10.0)]
    new = [model("claude-sonnet-5", 2.0, 10.0)]  # renamed styling, same model
    assert diff_snapshots("anthropic", old, new) == []


def test_new_model_is_major():
    old = [model("Sonnet 5")]
    new = [model("Sonnet 5"), model("Opus 5", 5.0, 25.0)]
    changes = diff_snapshots("anthropic", old, new)
    assert len(changes) == 1
    assert changes[0].kind == ADDED
    assert changes[0].model == "Opus 5"
    assert changes[0].severity == MAJOR


def test_removed_model_is_major():
    old = [model("Sonnet 5"), model("Opus 4")]
    new = [model("Sonnet 5")]
    changes = diff_snapshots("anthropic", old, new)
    assert [c.kind for c in changes] == [REMOVED]
    assert changes[0].model == "Opus 4"


def test_price_cut_is_detected_with_percentage():
    old = [model("Sonnet 5", 3.0, 15.0)]
    new = [model("Sonnet 5", 2.0, 10.0)]
    changes = diff_snapshots("anthropic", old, new)
    assert len(changes) == 2
    by_field = {c.field: c for c in changes}
    assert by_field["input"].pct == -1 / 3
    assert by_field["input"].severity == MAJOR
    assert "cut" in by_field["input"].describe()


def test_small_move_is_minor():
    old = [model("Sonnet 5", 2.00, 10.0)]
    new = [model("Sonnet 5", 2.02, 10.0)]  # 1% move
    changes = diff_snapshots("anthropic", old, new, major_price_move=0.05)
    assert len(changes) == 1
    assert changes[0].severity == MINOR


def test_threshold_boundary_counts_as_major():
    old = [model("Sonnet 5", 2.00, 10.0)]
    new = [model("Sonnet 5", 2.10, 10.0)]  # exactly 5%
    changes = diff_snapshots("anthropic", old, new, major_price_move=0.05)
    assert changes[0].severity == MAJOR


def test_price_appearing_from_null_is_major():
    old = [model("Grok 5", None, None)]
    new = [model("Grok 5", 3.0, 15.0)]
    changes = diff_snapshots("xai", old, new)
    assert len(changes) == 2
    assert all(c.kind == PRICE and c.severity == MAJOR for c in changes)


def test_context_window_change_is_reported():
    old = [model("Sonnet 5", ctx=200_000)]
    new = [model("Sonnet 5", ctx=1_000_000)]
    changes = diff_snapshots("anthropic", old, new)
    assert [c.kind for c in changes] == [CONTEXT]
    assert "1,000,000" in changes[0].describe()


def test_zero_old_price_does_not_divide_by_zero():
    old = [model("Free Model", 0.0, 0.0)]
    new = [model("Free Model", 1.0, 5.0)]
    changes = diff_snapshots("provider", old, new)
    assert all(c.severity == MAJOR for c in changes)
    assert all(c.pct is None for c in changes)


def test_major_changes_sort_first():
    old = [model("A", 2.00, 10.0), model("B", 1.0, 5.0)]
    new = [model("A", 2.01, 10.0), model("B", 1.0, 5.0), model("C", 9.0, 9.0)]
    changes = diff_snapshots("p", old, new)
    assert changes[0].severity == MAJOR
    assert changes[-1].severity == MINOR


def test_empty_new_snapshot_reports_everything_removed():
    old = [model("A"), model("B")]
    assert len(diff_snapshots("p", old, [])) == 2


def test_normalize_collapses_formatting():
    assert normalize("Claude Sonnet 5") == normalize("claude-sonnet-5")
    assert normalize("GPT-4.1 mini") == normalize("gpt 4.1 MINI")
    assert normalize("Gemini 3.5 Flash") != normalize("Gemini 3.5 Pro")


def test_every_change_renders_without_crashing():
    """describe() is called on every change in a run, so none may raise.

    The original bug: pct is None when a price appears from nothing or the old
    price was zero, and the format string assumed a number. The data tests
    passed; nobody had rendered the result.
    """
    cases = [
        ([model("A", 1.0, 5.0)], []),                       # removal
        ([], [model("A", 1.0, 5.0)]),                       # addition
        ([model("A", None, None)], [model("A", 1.0, 5.0)]), # price appears
        ([model("A", 1.0, 5.0)], [model("A", None, None)]), # price disappears
        ([model("A", 0.0, 0.0)], [model("A", 1.0, 5.0)]),   # divide by zero
        ([model("A", 3.0, 15.0)], [model("A", 2.0, 10.0)]), # ordinary cut
        ([model("A", ctx=200_000)], [model("A", ctx=1_000_000)]),
    ]
    rendered = 0
    for old, new in cases:
        for change in diff_snapshots("p", old, new):
            text = change.describe()
            assert text and "None" not in text, text
            rendered += 1
    assert rendered >= len(cases)
