import json
from pathlib import Path

from jsonschema import Draft202012Validator

from seebot.report.profiles import build_profiles


def _row(package_id: str, value: int, config: str = "a") -> dict:
    return {
        "package_id": package_id,
        "run_id": "pilot",
        "check_id": "PY-RUFF-001",
        "domain": "python",
        "status": "PASS",
        "config_sha256": config,
        "observed": {"finding_count": value, "nonblank_noncomment_lines": 1000},
    }


def test_profiles_are_provisional_and_configuration_scoped() -> None:
    packages = [
        {"package_id": f"tool-{index}", "run_id": "pilot", "languages": ["python"]}
        for index in range(4)
    ]
    rows = [_row("tool-0", 1), _row("tool-1", 2), _row("tool-2", 3), _row("tool-3", 99, "b")]
    profiles = build_profiles(packages, rows)
    first = profiles["profiles"][0]["languages"][0]["metrics"][0]
    isolated = profiles["profiles"][3]["languages"][0]["metrics"][0]
    assert first["cohort_size"] == 3
    assert first["interpretation"] == "provisional"
    assert isolated["cohort_size"] == 1
    assert isolated["interpretation"] == "insufficient"


def test_published_profiles_match_schema() -> None:
    root = Path(__file__).resolve().parents[2]
    schema = json.loads((root / "schemas" / "profiles.schema.json").read_text())
    profiles = json.loads((root / "web" / "public" / "data" / "profiles.json").read_text())
    Draft202012Validator(schema).validate(profiles)
