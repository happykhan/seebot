"""The bcqa command-line interface."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from bioconda_audit.cohort.downloads import fetch_window
from bioconda_audit.cohort.rank import rank_downloads
from bioconda_audit.evidence import ProbeSpec, run_probe
from bioconda_audit.manifests import load_yaml, validate_manifest, write_template
from bioconda_audit.normalize.results import normalize_run
from bioconda_audit.source.fetch import download_verified, extract_safe
from bioconda_audit.source.inventory import inventory_tree

ROOT = Path(__file__).resolve().parents[2]
console = Console()
app = typer.Typer(no_args_is_help=True, help="Reproducible Bioconda software audits.")
cohort_app = typer.Typer(no_args_is_help=True)
manifest_app = typer.Typer(no_args_is_help=True)
recipe_app = typer.Typer(no_args_is_help=True)
source_app = typer.Typer(no_args_is_help=True)
audit_app = typer.Typer(no_args_is_help=True)
results_app = typer.Typer(no_args_is_help=True)
report_app = typer.Typer(no_args_is_help=True)
batch_app = typer.Typer(no_args_is_help=True)
app.add_typer(cohort_app, name="cohort")
app.add_typer(manifest_app, name="manifest")
app.add_typer(recipe_app, name="recipe")
app.add_typer(source_app, name="source")
app.add_typer(audit_app, name="audit")
app.add_typer(results_app, name="results")
app.add_typer(report_app, name="report")
app.add_typer(batch_app, name="batch")


@dataclass
class Options:
    dry_run: bool
    verbose: bool
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
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    output_directory: Annotated[
        Path, typer.Option("--output-directory", help="Root for generated output.")
    ] = ROOT,
    run_id: Annotated[
        str, typer.Option("--run-id", help="Immutable audit run identifier.")
    ] = "local",
    resume: Annotated[bool, typer.Option("--resume/--no-resume")] = True,
    force: Annotated[bool, typer.Option("--force", help="Replace completed evidence.")] = False,
) -> None:
    """Global options are inherited by every subcommand."""
    ctx.obj = Options(dry_run, verbose, output_directory.resolve(), run_id, resume, force)


def options(ctx: typer.Context) -> Options:
    return ctx.ensure_object(Options)


def resolve_manifest(value: Path) -> Path:
    if value.exists():
        return value.resolve()
    candidate = ROOT / "manifests" / "packages" / f"{value}.yaml"
    if candidate.exists():
        return candidate.resolve()
    raise typer.BadParameter(f"No package manifest found for {value}")


def package_id(manifest: dict[str, Any]) -> str:
    package = manifest["package"]["name"]
    bioconda = manifest["bioconda"]
    version = bioconda["version"] or "UNKNOWN"
    build = bioconda["build"] or "UNKNOWN"
    return f"{package}__{version}__{build}__{bioconda['subdir']}"


@cohort_app.command("fetch")
def cohort_fetch(
    ctx: typer.Context,
    latest_complete_month: Annotated[bool, typer.Option("--latest-complete-month")] = True,
    months: Annotated[int, typer.Option(min=1, max=60)] = 12,
) -> None:
    """Fetch exactly N complete months from the official Anaconda dataset."""
    del latest_complete_month  # only conservative discovery is implemented
    opts = options(ctx)
    output = opts.output_directory / "data" / "raw" / "anaconda-downloads"
    manifest = fetch_window(output, months=months, dry_run=opts.dry_run)
    object_count = len(manifest["objects"]) if isinstance(manifest["objects"], list) else 0
    console.print(
        f"Selected {manifest['period_start']} through {manifest['period_end']} "
        f"({object_count} daily objects)."
    )


@cohort_app.command("rank")
def cohort_rank(
    ctx: typer.Context,
    channel: Annotated[str, typer.Option()] = "bioconda",
    top: Annotated[int, typer.Option(min=1)] = 300,
) -> None:
    opts = options(ctx)
    output = opts.output_directory / "data" / "cohort" / "cohort-ranked.csv"
    if opts.dry_run:
        console.print(f"Would aggregate local official Parquet inputs into {output}")
        return
    query_hash = rank_downloads(
        opts.output_directory / "data" / "raw" / "anaconda-downloads", output, channel, top
    )
    (output.with_suffix(".query.sha256")).write_text(query_hash + "\n", encoding="utf-8")
    console.print(f"Wrote {output} (query {query_hash}).")


@cohort_app.command("freeze")
def cohort_freeze(
    ctx: typer.Context,
    output: Annotated[Path, typer.Option()] = Path("data/cohort/cohort-candidates.csv"),
) -> None:
    opts = options(ctx)
    source = opts.output_directory / "data" / "cohort" / "cohort-ranked.csv"
    target = output if output.is_absolute() else opts.output_directory / output
    if opts.dry_run:
        console.print(f"Would freeze {source} as {target}")
        return
    if not source.exists():
        raise typer.BadParameter(f"Ranked cohort does not exist: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    console.print(f"Frozen candidate table: {target}")


@manifest_app.command("init")
def manifest_init(ctx: typer.Context, package: str) -> None:
    opts = options(ctx)
    target = opts.output_directory / "manifests" / "packages" / f"{package}.yaml"
    if target.exists() and not opts.force:
        raise typer.BadParameter(f"Manifest exists; pass --force before the command: {target}")
    if opts.dry_run:
        console.print(f"Would create {target}")
        return
    write_template(package, target)
    console.print(f"Created unreviewed manifest: {target}")


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
    paths = sorted((ROOT / "manifests" / "packages").glob("*.yaml"))
    failed = 0
    for path in paths:
        errors = validate_manifest(path)
        if errors:
            failed += 1
            console.print(f"[red]Invalid[/red] {path}: {'; '.join(errors)}")
        else:
            console.print(f"[green]Valid[/green] {path}")
    if failed:
        raise typer.Exit(1)
    console.print(f"Validated {len(paths)} package manifest(s).")


@recipe_app.command("fetch")
def recipe_fetch(ctx: typer.Context, package: Path) -> None:
    """Record the bounded recipe checkout task without guessing render semantics."""
    del ctx
    manifest = load_yaml(resolve_manifest(package))
    commit = manifest["bioconda"]["recipes_commit"]
    if not commit:
        console.print("[yellow]NOT_RUN[/yellow]: manifest has no reviewed recipes_commit.")
        raise typer.Exit(2)
    console.print(
        f"Recipe fetch is pinned to {commit}; use the source-resolver workflow for the pilot."
    )


@source_app.command("fetch")
def source_fetch(ctx: typer.Context, package: Path) -> None:
    opts = options(ctx)
    manifest_path = resolve_manifest(package)
    manifest = load_yaml(manifest_path)
    source = manifest["release_source"]
    if not source["source_url"] or not source["source_sha256"]:
        console.print("[yellow]NOT_RUN[/yellow]: source URL/checksum has not been reviewed.")
        raise typer.Exit(2)
    archive = opts.output_directory / "work" / package_id(manifest) / "source.archive"
    extracted = archive.parent / "source"
    if opts.dry_run:
        console.print(f"Would download, verify, and safely extract {source['source_url']}")
        return
    download_verified(source["source_url"], archive, source["source_sha256"])
    extract_safe(archive, extracted)
    console.print(f"Verified and extracted source to {extracted}")


@source_app.command("inventory")
def source_inventory(ctx: typer.Context, package: Path) -> None:
    opts = options(ctx)
    manifest = load_yaml(resolve_manifest(package))
    root = opts.output_directory / "work" / package_id(manifest) / "source"
    if not root.exists():
        raise typer.BadParameter(f"No extracted release source: {root}")
    excluded = [Path(value) for value in manifest["source_layout"]["excluded_paths"]]
    rows = inventory_tree(root, excluded)
    target = root.parent / "source-inventory.json"
    if not opts.dry_run:
        target.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    console.print(f"Inventoried {len(rows)} files into {target}")


def resolved_command(command: list[str], manifest_path: Path) -> list[str]:
    resolved: list[str] = []
    for value in command:
        candidate = manifest_path.parent / value
        resolved.append(str(candidate.resolve()) if candidate.exists() else value)
    return resolved


@audit_app.command("cli")
def audit_cli(ctx: typer.Context, package: Path) -> None:
    opts = options(ctx)
    manifest_path = resolve_manifest(package)
    manifest = load_yaml(manifest_path)
    errors = validate_manifest(manifest_path)
    if errors:
        raise typer.BadParameter("Manifest is invalid: " + "; ".join(errors))
    cli = manifest["cli"]
    probes: list[ProbeSpec] = []
    pkg_id = package_id(manifest)
    for command in cli["help_commands"]:
        probes.append(
            ProbeSpec(
                pkg_id,
                "CLI-HELP-001",
                resolved_command(command, manifest_path),
                [0],
                cli["timeout_seconds"],
            )
        )
    for command in cli["version_commands"]:
        probes.append(
            ProbeSpec(
                pkg_id,
                "CLI-VERSION-001",
                resolved_command(command, manifest_path),
                [0],
                cli["timeout_seconds"],
            )
        )
    if cli["invalid_option_command"]:
        probes.append(
            ProbeSpec(
                pkg_id,
                "CLI-INVALID-001",
                resolved_command(cli["invalid_option_command"], manifest_path),
                [1, 2, 64],
                cli["timeout_seconds"],
            )
        )
    table = Table("Check", "Status", "Exit code")
    for probe in probes:
        if opts.dry_run:
            table.add_row(probe.check_id, "NOT_RUN", "-")
            continue
        result = run_probe(
            probe,
            run_id=opts.run_id,
            evidence_root=opts.output_directory / "evidence",
            config_path=ROOT / "config" / "rubric.yaml",
            force=opts.force,
        )
        table.add_row(result.check_id, result.status.value, str(result.observed.get("exit_code")))
    console.print(table)


def not_run(domain: str) -> None:
    console.print(
        f"[yellow]NOT_RUN[/yellow]: {domain} audit is scaffolded but not enabled "
        "before pilot calibration."
    )


@audit_app.command("repository")
def audit_repository(package: Path) -> None:
    del package
    not_run("repository")


@audit_app.command("python")
def audit_python(package: Path) -> None:
    del package
    not_run("Python")


@audit_app.command("install")
def audit_install(package: Path) -> None:
    del package
    not_run("installation")


@audit_app.command("all")
def audit_all(ctx: typer.Context, package: Path) -> None:
    audit_cli(ctx, package)
    not_run("remaining pilot domains")


@results_app.command("normalize")
def results_normalize(ctx: typer.Context) -> None:
    opts = options(ctx)
    if opts.dry_run:
        console.print(f"Would normalize completed evidence for {opts.run_id}")
        return
    json_path, csv_path = normalize_run(
        opts.output_directory / "evidence", opts.output_directory / "results", opts.run_id
    )
    console.print(f"Wrote {json_path} and {csv_path}")


@report_app.command("build")
def report_build(ctx: typer.Context) -> None:
    opts = options(ctx)
    source = opts.output_directory / "results" / opts.run_id / "checks.json"
    target = ROOT / "web" / "public" / "data" / "checks.json"
    if not source.exists():
        raise typer.BadParameter(f"Normalize the run first: {source}")
    if not opts.dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    console.print(f"Prepared web application dataset: {target}")


@batch_app.command("run")
def batch_run(
    cohort: Annotated[Path, typer.Option()], jobs: Annotated[int, typer.Option(min=1)] = 4
) -> None:
    del cohort, jobs
    console.print(
        "[yellow]NOT_RUN[/yellow]: batch execution is locked until the ten-package pilot is frozen."
    )


if __name__ == "__main__":
    app()
