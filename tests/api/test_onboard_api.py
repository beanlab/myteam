from __future__ import annotations

from pathlib import Path

from myteam import onboard


def test_onboard_renders_application_overview_first_and_walks_tree(tmp_path: Path) -> None:
    root = tmp_path / "governing_docs"
    (root / "scenarios" / "nested").mkdir(parents=True)
    (root / "application-overview.md").write_text("overview body\n", encoding="utf-8")
    (root / "scenarios" / "b.md").write_text("b body\n", encoding="utf-8")
    (root / "scenarios" / "a.md").write_text("a body\n", encoding="utf-8")
    (root / "scenarios" / "nested" / "c.md").write_text("c body\n", encoding="utf-8")

    rendered = onboard(root)

    assert rendered == (
        "----application-overview.md----\n"
        "overview body\n\n"
        "----scenarios/a.md----\n"
        "a body\n\n"
        "----scenarios/b.md----\n"
        "b body\n\n"
        "----scenarios/nested/c.md----\n"
        "c body"
    )
