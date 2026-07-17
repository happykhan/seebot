from pathlib import Path

from seebot.selection import select_manifests
from seebot.survey import survey_rows

ROOT = Path(__file__).parents[2]
MANIFESTS = ROOT / "manifests" / "packages"


def test_selection_supports_tool_category_and_language() -> None:
    tools = select_manifests(MANIFESTS, tools=["cutadapt"])
    assert [manifest["project"]["id"] for _, manifest in tools] == ["cutadapt"]
    categories = select_manifests(MANIFESTS, categories=["read preprocessing"])
    assert {manifest["project"]["id"] for _, manifest in categories} == {
        "cutadapt",
        "fastp",
    }
    languages = select_manifests(MANIFESTS, languages=["rust"])
    assert {manifest["project"]["id"] for _, manifest in languages} == {"salmon", "yacrd"}


def test_survey_preserves_manifest_identity_and_status() -> None:
    rows = survey_rows(MANIFESTS, tools=["cutadapt"], include_excluded=True)
    assert rows[0]["project_id"] == "cutadapt"
    assert rows[0]["curation_status"] == "reviewed"
    assert rows[0]["exclusion_code"] is None
