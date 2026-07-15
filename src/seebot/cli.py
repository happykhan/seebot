"""Command-line interface for deterministic Seebot collection and reporting."""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from seebot.cohort.downloads import fetch_window
from seebot.cohort.rank import rank_downloads
from seebot.fixtures import validate_catalogue
from seebot.manifests import load_yaml, validate_manifest, write_template
from seebot.normalize.results import normalize_run, rebuild_global_results
from seebot.selection import select_manifests
from seebot.storage import directory_size, format_bytes, prune_owned_directory
from seebot.survey import SURVEY_FIELDS, survey_rows

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIRECTORY = ROOT / "manifests" / "packages"
SNAPSHOT_DATE = "2026-07-01"

console = Console()
app = typer.Typer(no_args_is_help=True, help="Evidence-based scientific software observations.")
cohort_app = typer.Typer(no_args_is_help=True)
manifest_app = typer.Typer(no_args_is_help=True)
fixture_app = typer.Typer(no_args_is_help=True)
survey_app = typer.Typer(no_args_is_help=True)
cache_app = typer.Typer(no_args_is_help=True)
audit_app = typer.Typer(no_args_is_help=True)
history_app = typer.Typer(no_args_is_help=True)
results_app = typer.Typer(no_args_is_help=True)
report_app = typer.Typer(no_args_is_help=True)
batch_app = typer.Typer(no_args_is_help=True)

for command_name, command_app in (
    ("cohort", cohort_app),
    ("manifest", manifest_app),
    ("fixture", fixture_app),
    ("survey", survey_app),
    ("cache", cache_app),
    ("audit", audit_app),
    ("history", history_app),
    ("results", results_app),
    ("report", report_app),
    ("batch", batch_app),
):
    app.add_typer(command_app, name=command_name)


@dataclass
class Options:
    dry_run: bool
    output_directory: Path
    run_id: str
    resume: bool
    force: bool


@app.callback()
def main(
    ctx: typer.Context,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Plan without changing files.")
    ] = False,
    output_directory: Annotated[
        Path, typer.Option("--output-directory", help="Root for generated output.")
    ] = ROOT,
    run_id: Annotated[str, typer.Option("--run-id")] = "current",
    resume: Annotated[bool, typer.Option("--resume/--no-resume")] = True,
    force: Annotated[bool, typer.Option("--force", help="Overwrite current results.")] = False,
) -> None:
    """Set options inherited by every subcommand."""
    ctx.obj = Options(dry_run, output_directory.resolve(), run_id, resume, force)


def options(ctx: typer.Context) -> Options:
    return ctx.ensure_object(Options)


def resolve_manifest(value: Path) -> Path:
    if value.exists():
        return value.resolve()
    candidate = MANIFEST_DIRECTORY / f"{value}.yaml"
    if candidate.exists():
        return candidate.resolve()
    raise typer.BadParameter(f"No project manifest found for {value}")


def selected_projects(
    tools: list[str] | None,
    categories: list[str] | None,
    languages: list[str] | None,
) -> list[tuple[Path, dict[str, Any]]]:
    try:
        return select_manifests(
            MANIFEST_DIRECTORY,
            tools=tools,
            categories=categories,
            languages=languages,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@cohort_app.command("fetch")
def cohort_fetch(
    ctx: typer.Context,
    months: Annotated[int, typer.Option(min=1, max=60)] = 12,
) -> None:
    """Fetch complete months of official Anaconda download records."""
    opts = options(ctx)
    output = opts.output_directory / "data" / "raw" / "anaconda-downloads"
    manifest = fetch_window(output, months=months, dry_run=opts.dry_run)
    objects = manifest["objects"]
    object_count = len(objects) if isinstance(objects, list) else 0
    console.print(
        f"Selected {manifest['period_start']} through {manifest['period_end']} "
        f"({object_count} daily objects)."
    )


@cohort_app.command("rank")
def cohort_rank(
    ctx: typer.Context,
    channel: Annotated[str, typer.Option()] = "bioconda",
    top: Annotated[int, typer.Option(min=300)] = 300,
) -> None:
    """Aggregate package downloads for discovery only; this is not a project metric."""
    opts = options(ctx)
    output = opts.output_directory / "data" / "cohort" / "cohort-ranked.csv"
    if opts.dry_run:
        console.print(f"Would aggregate local official Parquet inputs into {output}")
        return
    query_hash = rank_downloads(
        opts.output_directory / "data" / "raw" / "anaconda-downloads",
        output,
        channel,
        top,
    )
    output.with_suffix(".query.sha256").write_text(query_hash + "\n", encoding="utf-8")
    console.print(f"Wrote discovery candidates to {output} (query {query_hash}).")


@cohort_app.command("freeze")
def cohort_freeze(
    ctx: typer.Context,
    output: Annotated[Path, typer.Option()] = Path("data/cohort/cohort-candidates.csv"),
) -> None:
    """Copy the reviewed discovery table into the candidate input."""
    opts = options(ctx)
    source = opts.output_directory / "data" / "cohort" / "cohort-ranked.csv"
    target = output if output.is_absolute() else opts.output_directory / output
    if opts.dry_run:
        console.print(f"Would freeze {source} as {target}")
        return
    if not source.exists():
        raise typer.BadParameter(f"Ranked discovery table does not exist: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    console.print(f"Frozen candidate table: {target}")


@manifest_app.command("init")
def manifest_init(ctx: typer.Context, project: str) -> None:
    opts = options(ctx)
    target = opts.output_directory / "manifests" / "packages" / f"{project}.yaml"
    if target.exists() and not opts.force:
        raise typer.BadParameter(f"Manifest exists; pass --force before the command: {target}")
    if opts.dry_run:
        console.print(f"Would create {target}")
        return
    write_template(project, target)
    console.print(f"Created unreviewed project manifest: {target}")


@manifest_app.command("validate")
def manifest_validate(path: Path) -> None:
    target = resolve_manifest(path)
    errors = validate_manifest(target)
    if errors:
        for error in errors:
            console.print(f"[red]ERROR[/red] {error}")
        raise typer.Exit(1)
    console.print(f"[green]Valid[/green] {target}")


@manifest_app.command("validate-all")
def manifest_validate_all() -> None:
    failed = 0
    paths = sorted(MANIFEST_DIRECTORY.glob("*.yaml"))
    for path in paths:
        errors = validate_manifest(path)
        if errors:
            failed += 1
            console.print(f"[red]Invalid[/red] {path}: {'; '.join(errors)}")
        else:
            console.print(f"[green]Valid[/green] {path}")
    if failed:
        raise typer.Exit(1)
    console.print(f"Validated {len(paths)} project manifest(s).")


@fixture_app.command("validate")
def fixture_validate() -> None:
    errors = validate_catalogue()
    if errors:
        for error in errors:
            console.print(f"[red]ERROR[/red] {error}")
        raise typer.Exit(1)
    console.print("[green]Valid[/green] shared fixture catalogue.")


@survey_app.command("export")
def survey_export(
    ctx: typer.Context,
    output: Annotated[Path, typer.Option()] = Path("data/cohort/interface-survey.csv"),
    tool: Annotated[list[str] | None, typer.Option("--tool")] = None,
    category: Annotated[list[str] | None, typer.Option("--category")] = None,
    language: Annotated[list[str] | None, typer.Option("--language")] = None,
) -> None:
    """Export the metadata-first interface and fixture survey."""
    opts = options(ctx)
    target = output if output.is_absolute() else opts.output_directory / output
    rows = survey_rows(
        MANIFEST_DIRECTORY,
        tools=tool,
        categories=category,
        languages=language,
        include_excluded=True,
    )
    if opts.dry_run:
        console.print(f"Would write {len(rows)} survey row(s) to {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SURVEY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    console.print(f"Wrote {len(rows)} survey row(s) to {target}")


@survey_app.command("list")
def survey_list(
    tool: Annotated[list[str] | None, typer.Option("--tool")] = None,
    category: Annotated[list[str] | None, typer.Option("--category")] = None,
    language: Annotated[list[str] | None, typer.Option("--language")] = None,
    include_excluded: Annotated[bool, typer.Option("--include-excluded")] = False,
) -> None:
    """List projects selected for survey or later rerun."""
    try:
        selected = select_manifests(
            MANIFEST_DIRECTORY,
            tools=tool,
            categories=category,
            languages=language,
            include_excluded=include_excluded,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    table = Table("Project", "Category", "Languages", "Curation")
    for _, manifest in selected:
        table.add_row(
            manifest["project"]["id"],
            manifest["project"]["primary_category"] or "unknown",
            ", ".join(sorted(manifest["source"]["language_roots"])) or "unknown",
            manifest["curation"]["status"],
        )
    console.print(table)


@cache_app.command("status")
def cache_status(ctx: typer.Context) -> None:
    opts = options(ctx)
    for label, path in (
        ("Seebot cache", opts.output_directory / ".seebot-cache"),
        ("Temporary work", opts.output_directory / "work"),
    ):
        console.print(f"{label}: {format_bytes(directory_size(path))} ({path})")


@cache_app.command("prune")
def cache_prune(
    ctx: typer.Context,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Remove Seebot-owned cache and work directories."),
    ] = False,
) -> None:
    """Remove only storage owned by Seebot, never global Pixi caches."""
    opts = options(ctx)
    if not yes:
        raise typer.BadParameter("Pass --yes to remove only .seebot-cache and work.")
    removed = 0
    for path in (opts.output_directory / ".seebot-cache", opts.output_directory / "work"):
        if opts.dry_run:
            console.print(f"Would remove Seebot-owned directory {path}")
        else:
            removed += prune_owned_directory(path)
    if not opts.dry_run:
        console.print(f"Removed {format_bytes(removed)} from Seebot-owned storage.")


@audit_app.command("plan")
def audit_plan(
    tool: Annotated[list[str] | None, typer.Option("--tool")] = None,
    category: Annotated[list[str] | None, typer.Option("--category")] = None,
    language: Annotated[list[str] | None, typer.Option("--language")] = None,
    check: Annotated[list[str] | None, typer.Option("--check")] = None,
) -> None:
    """Plan current-snapshot checks without installing or executing projects."""
    selected = selected_projects(tool, category, language)
    checks = sorted(set(check or ["repository", "source", "usage", "robustness"]))
    table = Table("Project", "Snapshot", "Checks", "Installer", "Valid run")
    for _, manifest in selected:
        table.add_row(
            manifest["project"]["id"],
            manifest["repository"]["snapshot_date"],
            ", ".join(checks),
            manifest["installation"]["adapter"],
            manifest["valid_run"]["status"],
        )
    console.print(table)


@history_app.command("plan")
def history_plan(
    tool: Annotated[list[str] | None, typer.Option("--tool")] = None,
    category: Annotated[list[str] | None, typer.Option("--category")] = None,
    language: Annotated[list[str] | None, typer.Option("--language")] = None,
    year: Annotated[list[int] | None, typer.Option("--year", min=2021, max=2025)] = None,
) -> None:
    """Plan historical source-only observations at 1 July snapshots."""
    selected = selected_projects(tool, category, language)
    years = sorted(set(year or [2021, 2022, 2023, 2024, 2025]))
    table = Table("Project", "Years", "Scope")
    for _, manifest in selected:
        table.add_row(manifest["project"]["id"], ", ".join(map(str, years)), "source only")
    console.print(table)


@results_app.command("normalize")
def results_normalize(ctx: typer.Context) -> None:
    opts = options(ctx)
    if opts.dry_run:
        console.print(f"Would normalize completed evidence for {opts.run_id}")
        return
    json_path, csv_path = normalize_run(
        opts.output_directory / "evidence",
        opts.output_directory / "results",
        opts.run_id,
    )
    console.print(f"Wrote {json_path} and {csv_path}")
    global_json, global_csv = rebuild_global_results(opts.output_directory / "results")
    console.print(f"Updated global table: {global_json} and {global_csv}")


@results_app.command("rebuild-global")
def results_rebuild_global(ctx: typer.Context) -> None:
    opts = options(ctx)
    if opts.dry_run:
        console.print("Would rebuild the global table from normalized runs")
        return
    json_path, csv_path = rebuild_global_results(opts.output_directory / "results")
    console.print(f"Wrote {json_path} and {csv_path}")


def build_dataset() -> dict[str, Any]:
    projects: list[dict[str, Any]] = []
    language_counts: dict[str, int] = {}
    for manifest_path in sorted(MANIFEST_DIRECTORY.glob("*.yaml")):
        manifest = load_yaml(manifest_path)
        project = manifest["project"]
        languages = sorted(manifest["source"]["language_roots"])
        for language in languages:
            language_counts[language] = language_counts.get(language, 0) + 1
        projects.append(
            {
                "id": project["id"],
                "name": project["name"],
                "description": project["description"],
                "category": project["primary_category"],
                "tags": project["tags"],
                "included": project["include"],
                "exclusion_code": project["exclusion_code"],
                "repository_url": manifest["repository"]["url"],
                "snapshot_date": manifest["repository"]["snapshot_date"],
                "languages": languages,
                "primary_executable": manifest["interfaces"]["primary"],
                "valid_run_status": manifest["valid_run"]["status"],
                "curation_status": manifest["curation"]["status"],
                "labels": {
                    "usage_exemplar": False,
                    "repository_practice_exemplar": False,
                    "complete_assessment": False,
                    "practice_exemplar": False,
                },
            }
        )
    return {
        "schema_version": 2,
        "snapshot_date": SNAPSHOT_DATE,
        "projects": projects,
        "summary": {
            "catalogued_projects": len(projects),
            "included_projects": sum(project["included"] for project in projects),
            "language_counts": dict(sorted(language_counts.items())),
            "labels": {
                "usage_exemplars": 0,
                "repository_practice_exemplars": 0,
                "complete_assessments": 0,
                "practice_exemplars": 0,
            },
        },
    }


@report_app.command("build")
def report_build(ctx: typer.Context) -> None:
    """Overwrite the current website dataset from validated project manifests."""
    opts = options(ctx)
    target = ROOT / "web" / "public" / "data" / "dataset.json"
    dataset = build_dataset()
    if opts.dry_run:
        console.print(f"Would write {len(dataset['projects'])} projects to {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")
    console.print(f"Prepared web application dataset: {target}")


@batch_app.command("run")
def batch_run(
    cohort: Annotated[Path, typer.Option()],
    jobs: Annotated[int, typer.Option(min=1)] = 4,
) -> None:
    """Keep bulk execution locked until survey, pilot, schemas, and exclusions are frozen."""
    del cohort, jobs
    console.print(
        "[yellow]NOT_RUN[/yellow]: bulk execution remains locked pending the internal "
        "ten-project reproducibility gate."
    )


if __name__ == "__main__":
    app()
