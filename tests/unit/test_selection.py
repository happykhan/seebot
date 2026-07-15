from pathlib import Path

from seebot.selection import select_manifests
from seebot.survey import survey_rows

ROOT = Path(__file__).parents[2]
MANIFESTS = ROOT / "manifests" / "packages"


def test_selection_supports_tool_category_and_language() -> None:
    tools = select_manifests(MANIFESTS, tools=["cutadapt"])
    assert [manifest["project"]["id"] for _, manifest in tools] == ["cutadapt"]
    categories = select_manifests(MANIFESTS, categories=["read_preprocessing"])
    assert [manifest["project"]["id"] for _, manifest in categories] == ["cutadapt"]
    languages = select_manifests(MANIFESTS, languages=["rust"])
    assert {manifest["project"]["id"] for _, manifest in languages} == {"rasusa", "sourmash"}


def test_survey_preserves_exclusions() -> None:
    rows = survey_rows(MANIFESTS, tools=["busco"], include_excluded=True)
    assert rows[0]["exclusion_code"] == "NO_PUBLIC_GITHUB_REPOSITORY"
