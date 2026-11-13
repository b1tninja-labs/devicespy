"""docs/uda-outline.md must list every UDA 2.0 clause the code cites, so a citation cannot drift to a
clause number that the PDF does not have."""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CITED = [
    "1.1.4",
    "1.2.2",
    "1.2.3",
    "1.2.4",
    "1.3.2",
    "1.3.3",
    "2.5",
    "3.2.5",
    "3.2.6",
    "4.1.2",
    "4.1.3",
    "4.1.4",
    "4.3.2",
]


def outline() -> dict[str, str]:
    rows = re.findall(
        r"^\| ([0-9A-Z][0-9A-Za-z.]*) \| (.+) \|$",
        (ROOT / "docs" / "uda-outline.md").read_text(encoding="utf-8"),
        re.M,
    )
    return dict(rows)


def test_uda_outline_lists_every_cited_clause_with_its_title():
    found = outline()
    assert len(found) >= 150
    missing = [c for c in CITED if c not in found]
    assert not missing
    assert found["1.2.3"].startswith("Device unavailable")
    assert found["4.3.2"].startswith("Unicast eventing")
    assert found["3.2.5"] == "Action error response"


def test_uda_outline_records_the_pdf_it_was_read_from():
    text = (ROOT / "docs" / "uda-outline.md").read_text(encoding="utf-8")
    assert "9aa6eb29dfcdbe8991a667f8c9a3f47d532438082354b79f5c744b4b7618f202" in text
    assert "2020-04-17" in text
