from __future__ import annotations

import pytest

from myteam import increase_headers


@pytest.mark.parametrize(
    ("content", "offset", "expected"),
    [
        ("# Heading\n", 1, "## Heading\n"),
        ("# Heading\n", 3, "#### Heading\n"),
        (
            "#\n ##\tTabbed\r\n   ### Closing ###  \n    # indented code\r\n"
            "#not-a-heading\nTitle\n---\n\n",
            2,
            "###\n ####\tTabbed\r\n   ##### Closing ###  \n    # indented code\r\n"
            "#not-a-heading\nTitle\n---\n\n",
        ),
        ("####### Existing\n", 2, "######### Existing\n"),
        ("## No final newline", 1, "### No final newline"),
    ],
)
def test_increase_headers_transforms_only_atx_opening_runs(
    content: str, offset: int, expected: str
) -> None:
    assert increase_headers(content, offset) == expected


def test_increase_headers_defaults_to_one() -> None:
    assert increase_headers("# Heading") == "## Heading"


def test_increase_headers_zero_returns_content_unchanged() -> None:
    content = "# Heading\r\n## Another\n"

    result = increase_headers(content, 0)

    assert result == content


@pytest.mark.parametrize(
    ("marker", "other_marker"),
    [("`", "~"), ("~", "`")],
)
def test_increase_headers_respects_fence_marker_and_opening_length(
    marker: str, other_marker: str
) -> None:
    opener = marker * 4
    content = (
        f"{opener} language\n"
        "# protected after opener\n"
        f"{other_marker * 5}\n"
        "# protected after mismatched marker\n"
        f"{marker * 3}\n"
        "# protected after short run\n"
        f"{marker * 5}\t \n"
        "# changed after valid closer\n"
    )

    assert increase_headers(content) == content.replace(
        "# changed after valid closer", "## changed after valid closer"
    )


@pytest.mark.parametrize("marker", ["`", "~"])
def test_increase_headers_protects_an_unclosed_fence_through_end_of_input(marker: str) -> None:
    content = f"   {marker * 3}\n# protected\r\n## also protected"

    assert increase_headers(content, 2) == content


def test_increase_headers_requires_a_standard_fence_closer() -> None:
    content = "```\n# protected\n``` trailing text\n# still protected\n```\n# changed\n"

    assert increase_headers(content) == content.replace("# changed", "## changed")


def test_backtick_fence_opener_cannot_have_a_backtick_in_its_info_string() -> None:
    content = "``` language`detail\n# changed because no fence opened\n"

    assert increase_headers(content) == content.replace("# changed", "## changed")


@pytest.mark.parametrize("content", [None, 1, b"# Heading"])
def test_increase_headers_rejects_non_string_content(content: object) -> None:
    with pytest.raises(TypeError):
        increase_headers(content)  # type: ignore[arg-type]


@pytest.mark.parametrize("offset", [1.5, "1", None, True, False])
def test_increase_headers_rejects_non_integer_offsets(offset: object) -> None:
    with pytest.raises(TypeError):
        increase_headers("# Heading", offset)  # type: ignore[arg-type]


def test_increase_headers_rejects_negative_offsets() -> None:
    with pytest.raises(ValueError):
        increase_headers("# Heading", -1)
