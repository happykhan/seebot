"""Metadata-first survey of ranked discovery candidates."""

from __future__ import annotations

import configparser
import csv
import json
import re
import subprocess
import threading
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version

from seebot.evidence import sha256_bytes

CUTOFF = datetime.fromisoformat("2026-07-01T23:59:59+00:00")
SUPPORTED_LANGUAGES = {"Python", "Perl", "C", "C++", "Rust", "Java", "Cython"}
HISTORICAL_DATES = (
    "2021-07-01",
    "2022-07-01",
    "2023-07-01",
    "2024-07-01",
    "2025-07-01",
)
GITHUB_PATTERN = re.compile(r"https?://(?:www\.)?github\.com/([^/\s]+)/([^/#?\s\"'<>]+)", re.I)
FIELDS = (
    "candidate_rank",
    "package_name",
    "download_count",
    "summary",
    "package_version_at_cutoff",
    "package_build_at_cutoff",
    "package_subdir",
    "artifact_basename",
    "artifact_sha256",
    "repository_url",
    "repository_mapping_source",
    "repository_archived",
    "snapshot_commit",
    "primary_language",
    "languages_json",
    "upstream_project_id",
    "executable_candidate",
    "executable_confidence",
    "interface_status",
    "interface_evidence_json",
    "input_families",
    "output_families",
    "data_requirement",
    "provisionally_eligible",
    "eligible_sequence",
    "first_200_eligible",
    "exclusion_code",
    "review_status",
    "notes",
)

INTERPRETER_COMMANDS = {
    "bash",
    "cd",
    "cmake",
    "echo",
    "java",
    "make",
    "perl",
    "pip",
    "python",
    "python3",
    "R",
    "Rscript",
}
CONFIG_PATHS = {
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "Cargo.toml",
    "build.gradle",
    "build.gradle.kts",
}


def _github_token() -> str | None:
    completed = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else None


def _cache_path(cache_root: Path, url: str) -> Path:
    return cache_root / f"{sha256_bytes(url.encode())}.json"


def _get_json(
    client: httpx.Client,
    url: str,
    cache_root: Path,
    *,
    headers: dict[str, str] | None = None,
) -> Any:
    target = _cache_path(cache_root, url)
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    response = client.get(url, headers=headers)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f".tmp-{threading.get_ident()}")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return payload


def _get_text(client: httpx.Client, url: str, cache_root: Path) -> str | None:
    target = cache_root / f"{sha256_bytes(url.encode())}.txt"
    if target.exists():
        return target.read_text(encoding="utf-8")
    response = client.get(url)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f".tmp-{threading.get_ident()}")
    temporary.write_text(response.text, encoding="utf-8")
    temporary.replace(target)
    return response.text


def _repository_url(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    for field in ("dev_url", "home", "doc_url", "source_url", "project_url"):
        value = payload.get(field)
        if not isinstance(value, str):
            continue
        match = GITHUB_PATTERN.search(value)
        if match:
            owner, repository = match.groups()
            repository = repository.removesuffix(".git")
            if owner.lower() in {"anaconda", "bioconda", "conda", "conda-forge"}:
                continue
            return f"https://github.com/{owner}/{repository}", f"anaconda:{field}"
    return None, None


def _recipe_text(package_name: str, client: httpx.Client, cache_root: Path) -> str | None:
    url = (
        "https://raw.githubusercontent.com/bioconda/bioconda-recipes/master/"
        f"recipes/{package_name}/meta.yaml"
    )
    try:
        return _get_text(client, url, cache_root)
    except httpx.HTTPError:
        return None


def _recipe_source_repository(text: str | None) -> tuple[str | None, str | None]:
    """Use recipe source only to map a discovery package to its upstream project."""
    if not text:
        return None, None
    for match in GITHUB_PATTERN.finditer(text):
        owner, repository = match.groups()
        repository = repository.removesuffix(".git")
        if owner.lower() in {"anaconda", "bioconda", "conda", "conda-forge"}:
            continue
        return f"https://github.com/{owner}/{repository}", "bioconda:source_url"
    return None, None


def _recipe_executables(text: str | None) -> list[str]:
    if not text:
        return []
    names: set[str] = set()
    in_commands = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("commands:"):
            in_commands = True
            continue
        if in_commands and stripped and not stripped.startswith(("-", "#")):
            in_commands = False
        if (
            not in_commands
            or not stripped.startswith("-")
            or not re.search(r"(?:^|\s)(?:--help|-h|--version|-version)(?:\s|$)", stripped)
        ):
            continue
        command = stripped[1:].strip().strip("'\"")
        token = command.split(maxsplit=1)[0] if command else ""
        token = Path(token).name
        if (
            token
            and token not in INTERPRETER_COMMANDS
            and not token.startswith(("$", "{{"))
            and re.fullmatch(r"[A-Za-z0-9_.+-]+", token)
        ):
            names.add(token)
    return sorted(names)


def _tree_paths(payload: Any) -> list[str]:
    if not isinstance(payload, dict) or payload.get("truncated") is True:
        return []
    return [
        str(row["path"])
        for row in payload.get("tree", [])
        if isinstance(row, dict) and row.get("type") == "blob" and row.get("path")
    ]


def _configuration_executables(path: str, text: str) -> list[str]:
    names: set[str] = set()
    try:
        if path == "pyproject.toml":
            payload = tomllib.loads(text)
            project = payload.get("project", {})
            for section in ("scripts", "gui-scripts"):
                values = project.get(section, {}) if isinstance(project, dict) else {}
                if isinstance(values, dict):
                    names.update(str(name) for name in values)
            poetry = payload.get("tool", {}).get("poetry", {})
            if isinstance(poetry, dict) and isinstance(poetry.get("scripts"), dict):
                names.update(str(name) for name in poetry["scripts"])
        elif path == "setup.cfg":
            parser = configparser.ConfigParser()
            parser.read_string(text)
            if parser.has_option("options.entry_points", "console_scripts"):
                for row in parser.get("options.entry_points", "console_scripts").splitlines():
                    if "=" in row:
                        names.add(row.split("=", 1)[0].strip())
        elif path == "Cargo.toml":
            payload = tomllib.loads(text)
            bins = payload.get("bin", [])
            if isinstance(bins, list):
                names.update(
                    str(row["name"]) for row in bins if isinstance(row, dict) and row.get("name")
                )
            package = payload.get("package", {})
            if isinstance(package, dict) and package.get("name"):
                names.add(str(package["name"]))
    except (configparser.Error, tomllib.TOMLDecodeError, KeyError, TypeError, ValueError):
        pass
    if path == "setup.py":
        for block in re.findall(r"console_scripts[^\[]*\[([^\]]*)\]", text, re.S):
            names.update(
                match.group(1)
                for match in re.finditer(r"['\"]([A-Za-z0-9_.+-]+)\s*=\s*[^'\"]+['\"]", block)
            )
    return sorted(name for name in names if re.fullmatch(r"[A-Za-z0-9_.+-]+", name))


def _classify_interface(
    *,
    package_name: str,
    summary: str,
    primary_language: str | None,
    tree_paths: list[str],
    configs: dict[str, str],
    readme: str,
    recipe_text: str | None,
) -> tuple[str, list[str], list[str], str | None]:
    """Return status, executables, evidence references, and exclusion code.

    This deliberately uses metadata and repository documentation only. It does not
    install or execute candidates.
    """
    executables: set[str] = set()
    evidence: list[str] = []
    for name in _recipe_executables(recipe_text):
        executables.add(name)
        evidence.append(f"bioconda-meta.yaml:test.commands:{name}")
    for path, text in configs.items():
        for name in _configuration_executables(path, text):
            executables.add(name)
            evidence.append(f"repository:{path}:declared-executable:{name}")
    aliases = {package_name, package_name.replace("-", "_"), package_name.replace("-", "")}
    for path in tree_paths:
        parts = Path(path).parts
        if len(parts) == 2 and parts[0].lower() in {"bin", "scripts"}:
            name = Path(path).name.removesuffix(".py").removesuffix(".pl")
            if name in aliases:
                executables.add(name)
                evidence.append(f"repository:{path}:launcher")
        if path == "src/main.rs":
            executables.add(package_name)
            evidence.append("repository:src/main.rs:rust-binary-entrypoint")
        elif path.startswith("src/bin/") and path.endswith(".rs"):
            executables.add(Path(path).stem)
            evidence.append(f"repository:{path}:rust-binary-entrypoint")
    lowered = f"{summary}\n{readme[:20000]}".lower()
    if readme and any(
        term in lowered for term in ("usage", "command line", "command-line", "synopsis")
    ):
        for alias in aliases:
            if re.search(
                rf"(?im)^\s*(?:[$>]\s*)?{re.escape(alias)}\s+(?:--?[A-Za-z]|[./A-Za-z0-9])",
                readme,
            ):
                executables.add(package_name)
                evidence.append("repository:README:documented-command")
                break
    explicit_library = any(
        phrase in lowered
        for phrase in (
            "python library",
            "perl module",
            "c++ library",
            "header-only library",
            "bindings and python interface",
            "api bindings",
            "library for",
            "interface for interactions",
        )
    )
    explicit_data = any(
        phrase in lowered for phrase in ("data package", "data-only", "reference data package")
    )
    explicit_workflow_collection = package_name.startswith("snakemake-interface-") or any(
        phrase in lowered for phrase in ("workflow collection", "collection of workflows")
    )
    if explicit_data:
        return "excluded", [], ["upstream-description:data-only"], "DATA_ONLY"
    if explicit_workflow_collection:
        return "excluded", [], ["upstream-description:workflow-collection"], "WORKFLOW_COLLECTION"
    if executables:
        return "confirmed_end_user_cli", sorted(executables), sorted(set(evidence)), None
    if explicit_library or package_name.startswith("perl-"):
        return "excluded", [], ["upstream-description:library-only"], "LIBRARY_ONLY"
    if tree_paths:
        return "excluded", [], ["repository-metadata:no-end-user-cli-found"], "NO_END_USER_CLI"
    return "unknown", [], ["repository-metadata:tree-unavailable"], "OTHER_WITH_NOTE"


def _artifact_at_cutoff(payload: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[tuple[Version, datetime, dict[str, Any]]] = []
    for row in payload.get("files", []):
        attrs = row.get("attrs") or {}
        if attrs.get("subdir") not in {"linux-64", "noarch"}:
            continue
        try:
            uploaded = datetime.fromisoformat(str(row["upload_time"]))
            version = Version(str(row["version"]))
        except (InvalidVersion, KeyError, ValueError):
            continue
        if uploaded <= CUTOFF:
            candidates.append((version, uploaded, row))
    return max(candidates, default=(Version("0"), CUTOFF, None), key=lambda item: item[:2])[2]


def _format_families(text: str) -> tuple[str, str]:
    lowered = text.lower()
    inputs = [
        label
        for label, tokens in {
            "FASTQ": ("fastq", "read trimming", "sequencing reads"),
            "FASTA": ("fasta", "genome", "sequence alignment", "assembly"),
            "SAM/BAM/CRAM": ("sam", "bam", "cram", "alignment file"),
            "VCF": ("vcf", "variant"),
            "GFF": ("gff", "annotation"),
            "BED": ("bed", "genomic interval"),
            "Newick": ("newick", "phylogen"),
        }.items()
        if any(token in lowered for token in tokens)
    ]
    outputs = list(inputs)
    if any(token in lowered for token in ("report", "visuali", "plot", "quality control")):
        outputs.append("report/plot")
    return ";".join(dict.fromkeys(inputs)) or "UNKNOWN", ";".join(
        dict.fromkeys(outputs)
    ) or "UNKNOWN"


def _survey_one(
    ranked: dict[str, str], client: httpx.Client, cache_root: Path, token: str | None
) -> dict[str, Any]:
    package_name = ranked["pkg_name"]
    notes: list[str] = []
    try:
        package = _get_json(
            client,
            f"https://api.anaconda.org/package/bioconda/{package_name}",
            cache_root / "anaconda",
        )
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        package = None
        notes.append(f"Anaconda metadata error: {type(exc).__name__}")
    if not isinstance(package, dict):
        package = {}
    recipe_text = _recipe_text(package_name, client, cache_root / "bioconda-mapping")
    repository_url, mapping_source = _repository_url(package)
    if repository_url is None:
        repository_url, mapping_source = _recipe_source_repository(recipe_text)
    repository: dict[str, Any] = {}
    languages: dict[str, int] = {}
    snapshot_commit: str | None = None
    tree_paths: list[str] = []
    configuration_text: dict[str, str] = {}
    readme_text = ""
    github_headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        github_headers["Authorization"] = f"Bearer {token}"
    if repository_url:
        match = GITHUB_PATTERN.search(repository_url)
        assert match is not None
        owner, repo = match.groups()
        repo = repo.removesuffix(".git")
        base = f"https://api.github.com/repos/{owner}/{repo}"
        try:
            repository_payload = _get_json(
                client, base, cache_root / "github", headers=github_headers
            )
            if isinstance(repository_payload, dict):
                repository = repository_payload
                languages_payload = _get_json(
                    client, f"{base}/languages", cache_root / "github", headers=github_headers
                )
                if isinstance(languages_payload, dict):
                    languages = {str(key): int(value) for key, value in languages_payload.items()}
                commits = _get_json(
                    client,
                    f"{base}/commits?until=2026-07-01T23:59:59Z&per_page=1",
                    cache_root / "github",
                    headers=github_headers,
                )
                if isinstance(commits, list) and commits:
                    snapshot_commit = commits[0].get("sha")
                if snapshot_commit:
                    tree_payload = _get_json(
                        client,
                        f"{base}/git/trees/{snapshot_commit}?recursive=1",
                        cache_root / "github",
                        headers=github_headers,
                    )
                    tree_paths = _tree_paths(tree_payload)
                    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}/{snapshot_commit}"
                    root_paths = set(tree_paths)
                    for config_path in sorted(CONFIG_PATHS & root_paths):
                        text = _get_text(
                            client,
                            f"{raw_base}/{config_path}",
                            cache_root / "github-raw",
                        )
                        if text is not None:
                            configuration_text[config_path] = text
                    readmes = sorted(
                        path
                        for path in tree_paths
                        if "/" not in path and path.lower().startswith("readme")
                    )
                    if readmes:
                        readme_text = (
                            _get_text(
                                client,
                                f"{raw_base}/{readmes[0]}",
                                cache_root / "github-raw",
                            )
                            or ""
                        )
            else:
                notes.append("Mapped GitHub repository was unavailable")
        except (
            httpx.HTTPError,
            httpx.InvalidURL,
            json.JSONDecodeError,
            KeyError,
            ValueError,
        ) as exc:
            notes.append(f"GitHub metadata error: {type(exc).__name__}")
    artifact = _artifact_at_cutoff(package)
    attrs = artifact.get("attrs", {}) if artifact else {}
    summary = str(package.get("summary") or repository.get("description") or "")
    inputs, outputs = _format_families(summary)
    primary_language = repository.get("language")
    interface_status, executable_names, interface_evidence, interface_exclusion = (
        _classify_interface(
            package_name=package_name,
            summary=summary,
            primary_language=primary_language,
            tree_paths=tree_paths,
            configs=configuration_text,
            readme=readme_text,
            recipe_text=recipe_text,
        )
    )
    exclusion_code: str | None = None
    eligible = False
    if package_name.startswith("r-") or primary_language == "R":
        exclusion_code = "PRIMARY_LANGUAGE_R"
    elif repository_url is None or not snapshot_commit:
        exclusion_code = "SNAPSHOT_UNRESOLVED"
    elif not primary_language:
        exclusion_code = "OTHER_WITH_NOTE"
    elif primary_language and primary_language not in SUPPORTED_LANGUAGES:
        exclusion_code = "UNSUPPORTED_PRIMARY_LANGUAGE"
    elif interface_status != "confirmed_end_user_cli":
        exclusion_code = interface_exclusion
    else:
        eligible = True
    artifact_attrs = artifact.get("attrs", {}) if artifact else {}
    artifact_basename = artifact.get("basename") if artifact else None
    artifact_sha256 = (
        artifact_attrs.get("sha256") or (artifact.get("sha256") if artifact else None) or None
    )
    return {
        "candidate_rank": int(ranked["candidate_rank"]),
        "package_name": package_name,
        "download_count": int(ranked["download_count"]),
        "summary": summary or None,
        "package_version_at_cutoff": artifact.get("version") if artifact else None,
        "package_build_at_cutoff": attrs.get("build"),
        "package_subdir": attrs.get("subdir"),
        "artifact_basename": artifact_basename,
        "artifact_sha256": artifact_sha256,
        "repository_url": repository_url,
        "repository_mapping_source": mapping_source,
        "repository_archived": repository.get("archived"),
        "snapshot_commit": snapshot_commit,
        "primary_language": primary_language,
        "languages_json": json.dumps(languages, sort_keys=True),
        "upstream_project_id": None,
        "executable_candidate": ";".join(executable_names) or None,
        "executable_confidence": "explicit_metadata" if executable_names else "none",
        "interface_status": interface_status,
        "interface_evidence_json": json.dumps(interface_evidence, sort_keys=True),
        "input_families": inputs,
        "output_families": outputs,
        "data_requirement": "UNKNOWN",
        "provisionally_eligible": eligible,
        "eligible_sequence": None,
        "first_200_eligible": False,
        "exclusion_code": exclusion_code,
        "review_status": "metadata_interface_reviewed",
        "notes": "; ".join(notes) or None,
    }


def collect_candidate_survey(
    ranked_path: Path,
    output_json: Path,
    output_csv: Path,
    cache_root: Path,
    *,
    limit: int = 350,
    workers: int = 8,
) -> list[dict[str, Any]]:
    with ranked_path.open(newline="", encoding="utf-8") as handle:
        ranked = list(csv.DictReader(handle))[:limit]
    token = _github_token()
    with (
        httpx.Client(follow_redirects=True, timeout=60) as client,
        ThreadPoolExecutor(max_workers=workers) as executor,
    ):
        rows = list(
            executor.map(
                lambda row: _survey_one(row, client, cache_root, token),
                ranked,
            )
        )
    rows.sort(key=lambda row: int(row["candidate_rank"]))
    eligible_repositories: set[str] = set()
    eligible_sequence = 0
    for row in rows:
        repository_url = row.get("repository_url")
        upstream_id = None
        if isinstance(repository_url, str) and repository_url:
            match = GITHUB_PATTERN.search(repository_url)
            if match:
                upstream_id = ".".join(part.lower() for part in match.groups())
        row["upstream_project_id"] = upstream_id
        if row["provisionally_eligible"] and upstream_id in eligible_repositories:
            row["provisionally_eligible"] = False
            row["exclusion_code"] = "DUPLICATE_PROJECT_ALIAS"
            row["notes"] = "; ".join(
                value
                for value in (row.get("notes"), "Earlier eligible package mapped to same upstream")
                if value
            )
        elif row["provisionally_eligible"]:
            if upstream_id:
                eligible_repositories.add(upstream_id)
            eligible_sequence += 1
            row["eligible_sequence"] = eligible_sequence
            row["first_200_eligible"] = eligible_sequence <= 200
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def resolve_historical_commits(
    survey_path: Path,
    output_path: Path,
    cache_root: Path,
    project_names: set[str],
) -> dict[str, dict[str, str | None]]:
    """Resolve exact source-only snapshots for a reviewed project selection."""
    rows = json.loads(survey_path.read_text(encoding="utf-8"))
    selected = [row for row in rows if row.get("package_name") in project_names]
    missing = project_names - {str(row["package_name"]) for row in selected}
    if missing:
        raise ValueError("Projects absent from candidate survey: " + ", ".join(sorted(missing)))
    token = _github_token()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resolved: dict[str, dict[str, str | None]] = {}
    with httpx.Client(follow_redirects=True, timeout=60) as client:
        for row in selected:
            match = GITHUB_PATTERN.search(str(row["repository_url"]))
            if match is None:
                raise ValueError(f"Unresolved GitHub repository for {row['package_name']}")
            owner, repository = match.groups()
            base = f"https://api.github.com/repos/{owner}/{repository.removesuffix('.git')}"
            values: dict[str, str | None] = {}
            for snapshot_date in HISTORICAL_DATES:
                payload = _get_json(
                    client,
                    f"{base}/commits?until={snapshot_date}T23:59:59Z&per_page=1",
                    cache_root,
                    headers=headers,
                )
                values[snapshot_date] = (
                    str(payload[0]["sha"])
                    if isinstance(payload, list) and payload and payload[0].get("sha")
                    else None
                )
            resolved[str(row["package_name"])] = values
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(resolved, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved
