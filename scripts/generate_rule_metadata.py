#!/usr/bin/env python3
"""Generate public analyzer-rule help from the exact pinned analyzer releases."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/current/checks.json"
OUTPUT = ROOT / "web/src/ruleMetadata.ts"
VERSIONS = {"pylint": "4.0.6", "bandit": "1.9.4"}
CATEGORIES = {
    "C": "convention",
    "E": "error",
    "F": "fatal",
    "I": "information",
    "R": "refactor",
    "W": "warning",
}


def _run_json(command: list[str]) -> object:
    return json.loads(subprocess.run(command, check=True, text=True, capture_output=True).stdout)


def _observed_rules() -> dict[str, set[str]]:
    rules = {name: set() for name in ("ruff", "pylint", "bandit")}
    for result in json.loads(RESULTS.read_text(encoding="utf-8")):
        analyzer = result.get("tool", {}).get("name")
        if analyzer not in rules:
            continue
        rules[analyzer].update(item["rule"] for item in result.get("observed", {}).get("rules", []))
    return rules


def _plain(text: str) -> str:
    text = re.sub(r"``([^`]+)``", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", text)
    return " ".join(text.split()).strip()


def _concise(text: str, sentences: int = 3) -> str:
    plain = _plain(text)
    parts = re.split(r"(?<=[.!?])\s+", plain)
    return " ".join(parts[:sentences])


def _ruff_metadata(observed: set[str]) -> dict[str, dict[str, str]]:
    rows = _run_json([str(ROOT / ".venv/bin/ruff"), "rule", "--all", "--output-format", "json"])
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        if row["code"] not in observed:
            continue
        match = re.search(r"## What it does\s+(.+?)(?:\n\n|\n##)", row["explanation"], re.DOTALL)
        description = _plain(match.group(1) if match else row["summary"])
        output[f"ruff:{row['code']}"] = {
            "description": description,
            "url": f"https://docs.astral.sh/ruff/rules/{row['name']}/",
        }
    if "invalid-syntax" in observed:
        output["ruff:invalid-syntax"] = {
            "description": (
                "The file could not be parsed as valid Python syntax, so Ruff could not "
                "complete normal rule analysis for it."
            ),
            "url": "https://docs.astral.sh/ruff/linter/",
        }
    return output


def _pixi_json(package: str, source: str) -> object:
    pixi = shutil.which("pixi")
    if pixi is None:
        raise SystemExit("pixi is required to query the pinned analyzer metadata")
    return _run_json(
        [
            pixi,
            "exec",
            "--channel",
            "conda-forge",
            "-s",
            f"{package}={VERSIONS[package]}",
            "python",
            "-c",
            source,
        ]
    )


def _pylint_metadata(observed: set[str]) -> dict[str, dict[str, str]]:
    rows = _pixi_json(
        "pylint",
        "import json; from pylint.lint import PyLinter; "
        "l=PyLinter(); l.load_default_plugins(); l.initialize(); "
        "print(json.dumps([{'msgid':m.msgid,'symbol':m.symbol,'description':m.description} "
        "for m in l.msgs_store.messages]))",
    )
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        if row["symbol"] not in observed:
            continue
        category = CATEGORIES[row["msgid"][0]]
        output[f"pylint:{row['symbol']}"] = {
            "description": _plain(row["description"]),
            "url": f"https://pylint.readthedocs.io/en/latest/user_guide/messages/{category}/{row['symbol']}.html",
        }
    return output


def _bandit_metadata(observed: set[str]) -> dict[str, dict[str, str]]:
    source = (
        "import inspect,json\n"
        "from bandit.core.extension_loader import MANAGER\n"
        "out=[]\n"
        "for k,v in MANAGER.plugins_by_id.items():\n"
        " out.append({'id':k,'name':v.name,'doc':(v.plugin.__doc__ or "
        "inspect.getmodule(v.plugin).__doc__ or ''),'kind':'plugin'})\n"
        "for k,v in MANAGER.blacklist_by_id.items():\n"
        " out.append({'id':k,'name':v['name'],'doc':v['message'],'kind':'blacklist'})\n"
        "print(json.dumps(out))"
    )
    rows = _pixi_json(
        "bandit",
        source,
    )
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        if row["id"] not in observed:
            continue
        key = f"bandit:{row['id']}"
        if key in output:
            continue
        doc = row["doc"].strip()
        paragraphs = [
            part for part in re.split(r"\n\s*\n", doc) if part and not set(part) <= {"=", "-"}
        ]
        candidates = [
            part
            for part in paragraphs
            if row["id"] not in part[:120]
            and not part.lstrip().startswith(("..", ":", "**Config", "**B"))
        ]
        descriptive = next(
            (
                part
                for part in candidates
                if "specifically" in part.lower() or "this test will" in part.lower()
            ),
            next(
                (
                    part
                    for part in candidates
                    if "this plugin test" in part.lower() or "this pattern" in part.lower()
                ),
                candidates[0] if candidates else row["name"].replace("_", " "),
            ),
        )
        if row["kind"] == "blacklist":
            if 313 <= int(row["id"][1:]) <= 319:
                anchor = "b313-b319-xml"
            else:
                anchor = f"{row['id'].lower()}-{row['name'].lower().replace('_', '-')}"
            page = "blacklist_calls" if row["id"].startswith("B3") else "blacklist_imports"
            url = f"https://bandit.readthedocs.io/en/latest/blacklists/{page}.html#{anchor}"
        else:
            url = f"https://bandit.readthedocs.io/en/latest/plugins/{row['id'].lower()}_{row['name']}.html"
        if row["id"] == "B324":
            url = "https://bandit.readthedocs.io/en/latest/plugins/b324_hashlib.html"
        description = _concise(descriptive).replace("{name} module", "the reported module")
        description = description.replace("{name}", "the reported call")
        output[key] = {
            "description": description,
            "url": url,
        }
    return output


def main() -> None:
    observed = _observed_rules()
    metadata = {
        **_ruff_metadata(observed["ruff"]),
        **_pylint_metadata(observed["pylint"]),
        **_bandit_metadata(observed["bandit"]),
    }
    missing = sorted(
        f"{analyzer}:{rule}"
        for analyzer, rules in observed.items()
        for rule in rules
        if f"{analyzer}:{rule}" not in metadata
    )
    if missing:
        raise SystemExit("Missing analyzer metadata: " + ", ".join(missing))
    payload = json.dumps(dict(sorted(metadata.items())), indent=2, ensure_ascii=False)
    OUTPUT.write_text(
        "// Generated by scripts/generate_rule_metadata.py from pinned analyzer metadata.\n"
        "export interface RuleMetadata { description: string; url: string }\n\n"
        f"export const analyzerRuleMetadata: Record<string, RuleMetadata> = {payload}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
