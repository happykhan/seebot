"""The seebot command-line interface."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from seebot.analyzers.python import run_python_analyzers
from seebot.analyzers.repository import run_repository_observation
from seebot.cohort.downloads import fetch_window
from seebot.cohort.rank import rank_downloads
from seebot.evidence import (
    ContainerProbeSpec,
    ProbeSpec,
    run_container_probe,
    run_probe,
    sha256_file,
)
from seebot.manifests import load_yaml, validate_manifest, write_template
from seebot.normalize.results import normalize_run, rebuild_global_results
from seebot.recipes.checkout import fetch_recipe_file
from seebot.recipes.test_depth import write_recipe_test_observation
from seebot.report.awards import load_award_config, rank_packages, write_badges
from seebot.runtime.pixi import (
    PixiEnvironment,
    PixiProbeSpec,
    prepare_environment,
    run_pixi_probe,
)
from seebot.source.fetch import download_verified, extract_safe
from seebot.source.inventory import inventory_tree

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
    months: Annotated[int, typer.Option(min=1, max=60)] = 12,
) -> None:
    """Fetch exactly N complete months from the official Anaconda dataset."""
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
    """Preserve the original recipe from its reviewed immutable commit."""
    opts = options(ctx)
    manifest = load_yaml(resolve_manifest(package))
    commit = manifest["bioconda"]["recipes_commit"]
    if not commit:
        console.print("[yellow]NOT_RUN[/yellow]: manifest has no reviewed recipes_commit.")
        raise typer.Exit(2)
    target = opts.output_directory / "work" / package_id(manifest) / "recipe" / "meta.yaml"
    if target.exists() and not opts.force:
        console.print(f"Using preserved recipe: {target}")
        return
    if opts.dry_run:
        console.print(f"Would fetch {manifest['bioconda']['recipe_path']} at {commit}")
        return
    fetch_recipe_file(commit, manifest["bioconda"]["recipe_path"], target)
    console.print(f"Preserved pinned recipe: {target}")


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


def container_probe(
    manifest: dict[str, Any],
    *,
    check_id: str,
    domain: str,
    command: list[str],
    allowed_exit_codes: list[int],
    fixture_directory: Path | None = None,
    expected_stdout_contains: str | None = None,
    expected_output_sha256: dict[str, str] | None = None,
    manifest_path: Path | None = None,
) -> ContainerProbeSpec:
    runtime = manifest["runtime"]
    if runtime["backend"] != "container":
        raise typer.BadParameter("Manifest does not define a container runtime.")
    if not runtime["container_image"] or not runtime["container_digest"]:
        raise typer.BadParameter("Container image and digest must both be reviewed.")
    return ContainerProbeSpec(
        package_id=package_id(manifest),
        check_id=check_id,
        domain=domain,
        command=command,
        allowed_exit_codes=allowed_exit_codes,
        timeout_seconds=manifest["cli"]["timeout_seconds"],
        image=runtime["container_image"],
        digest=runtime["container_digest"],
        platform=runtime["platform"],
        fixture_directory=fixture_directory,
        expected_stdout_contains=expected_stdout_contains,
        expected_output_sha256=expected_output_sha256,
        manifest_sha256=sha256_file(manifest_path) if manifest_path else None,
    )


def package_pixi_environment(manifest: dict[str, Any], opts: Options) -> PixiEnvironment:
    runtime = manifest["runtime"]
    package_name = runtime["pixi_package"] or manifest["package"]["name"]
    version = manifest["bioconda"]["version"]
    if not version:
        raise typer.BadParameter("A reviewed package version is required for Pixi.")
    return prepare_environment(
        opts.output_directory / "work" / package_id(manifest) / "pixi-environment",
        package_name=package_name,
        version=str(version),
        channels=runtime["pixi_channels"],
    )


def pixi_probe(
    manifest: dict[str, Any],
    environment: PixiEnvironment,
    *,
    check_id: str,
    domain: str,
    command: list[str],
    allowed_exit_codes: list[int],
    fixture_directory: Path | None = None,
    expected_stdout_contains: str | None = None,
    expected_output_sha256: dict[str, str] | None = None,
    manifest_path: Path | None = None,
) -> PixiProbeSpec:
    return PixiProbeSpec(
        package_id=package_id(manifest),
        check_id=check_id,
        domain=domain,
        command=command,
        allowed_exit_codes=allowed_exit_codes,
        timeout_seconds=manifest["cli"]["timeout_seconds"],
        environment=environment,
        fixture_directory=fixture_directory,
        expected_stdout_contains=expected_stdout_contains,
        expected_output_sha256=expected_output_sha256,
        manifest_sha256=sha256_file(manifest_path) if manifest_path else None,
    )


def execute_container_probes(probes: list[ContainerProbeSpec], opts: Options) -> list[Any]:
    table = Table("Check", "Status", "Exit code")
    results = []
    for probe in probes:
        if opts.dry_run:
            table.add_row(probe.check_id, "NOT_RUN", "-")
            continue
        result = run_container_probe(
            probe,
            run_id=opts.run_id,
            evidence_root=opts.output_directory / "evidence",
            config_path=ROOT / "config" / "rubric.yaml",
            force=opts.force,
        )
        results.append(result)
        table.add_row(result.check_id, result.status.value, str(result.observed.get("exit_code")))
    console.print(table)
    return results


def execute_pixi_probes(probes: list[PixiProbeSpec], opts: Options) -> list[Any]:
    table = Table("Check", "Status", "Exit code")
    results = []
    for probe in probes:
        if opts.dry_run:
            table.add_row(probe.check_id, "NOT_RUN", "-")
            continue
        result = run_pixi_probe(
            probe,
            run_id=opts.run_id,
            evidence_root=opts.output_directory / "evidence",
            config_path=ROOT / "config" / "rubric.yaml",
            force=opts.force,
        )
        results.append(result)
        table.add_row(result.check_id, result.status.value, str(result.observed.get("exit_code")))
    console.print(table)
    return results


@audit_app.command("cli")
def audit_cli(ctx: typer.Context, package: Path) -> None:
    opts = options(ctx)
    manifest_path = resolve_manifest(package)
    manifest = load_yaml(manifest_path)
    errors = validate_manifest(manifest_path)
    if errors:
        raise typer.BadParameter("Manifest is invalid: " + "; ".join(errors))
    cli = manifest["cli"]
    if manifest["runtime"]["backend"] == "pixi":
        environment = package_pixi_environment(manifest, opts)
        probes: list[PixiProbeSpec] = []
        for command in cli["help_commands"]:
            probes.append(
                pixi_probe(
                    manifest,
                    environment,
                    check_id="CLI-HELP-001",
                    domain="cli",
                    command=command,
                    allowed_exit_codes=[0],
                    manifest_path=manifest_path,
                )
            )
        for command in cli["version_commands"]:
            probes.append(
                pixi_probe(
                    manifest,
                    environment,
                    check_id="CLI-VERSION-001",
                    domain="cli",
                    command=command,
                    allowed_exit_codes=[0],
                    expected_stdout_contains=str(manifest["bioconda"]["version"]),
                    manifest_path=manifest_path,
                )
            )
        if cli["invalid_option_command"]:
            probes.append(
                pixi_probe(
                    manifest,
                    environment,
                    check_id="CLI-INVALID-001",
                    domain="cli",
                    command=cli["invalid_option_command"],
                    allowed_exit_codes=[1, 2, 64],
                    manifest_path=manifest_path,
                )
            )
        execute_pixi_probes(probes, opts)
        return
    if manifest["runtime"]["backend"] == "container":
        container_probes: list[ContainerProbeSpec] = []
        for command in cli["help_commands"]:
            container_probes.append(
                container_probe(
                    manifest,
                    check_id="CLI-HELP-001",
                    domain="cli",
                    command=command,
                    allowed_exit_codes=[0],
                    manifest_path=manifest_path,
                )
            )
        for command in cli["version_commands"]:
            container_probes.append(
                container_probe(
                    manifest,
                    check_id="CLI-VERSION-001",
                    domain="cli",
                    command=command,
                    allowed_exit_codes=[0],
                    expected_stdout_contains=str(manifest["bioconda"]["version"]),
                    manifest_path=manifest_path,
                )
            )
        if cli["invalid_option_command"]:
            container_probes.append(
                container_probe(
                    manifest,
                    check_id="CLI-INVALID-001",
                    domain="cli",
                    command=cli["invalid_option_command"],
                    allowed_exit_codes=[1, 2, 64],
                    manifest_path=manifest_path,
                )
            )
        execute_container_probes(container_probes, opts)
        return

    native_probes: list[ProbeSpec] = []
    pkg_id = package_id(manifest)
    for command in cli["help_commands"]:
        native_probes.append(
            ProbeSpec(
                pkg_id,
                "CLI-HELP-001",
                resolved_command(command, manifest_path),
                [0],
                cli["timeout_seconds"],
            )
        )
    for command in cli["version_commands"]:
        native_probes.append(
            ProbeSpec(
                pkg_id,
                "CLI-VERSION-001",
                resolved_command(command, manifest_path),
                [0],
                cli["timeout_seconds"],
            )
        )
    if cli["invalid_option_command"]:
        native_probes.append(
            ProbeSpec(
                pkg_id,
                "CLI-INVALID-001",
                resolved_command(cli["invalid_option_command"], manifest_path),
                [1, 2, 64],
                cli["timeout_seconds"],
            )
        )
    table = Table("Check", "Status", "Exit code")
    for probe in native_probes:
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
def audit_repository(ctx: typer.Context, package: Path) -> None:
    opts = options(ctx)
    manifest_path = resolve_manifest(package)
    manifest = load_yaml(manifest_path)
    upstream = manifest["upstream"]
    if not upstream["repository_url"] or not upstream["default_branch_commit_at_audit"]:
        console.print("[yellow]NOT_RUN[/yellow]: upstream repository mapping is incomplete.")
        return
    if opts.dry_run:
        console.print(
            f"Would inspect {upstream['repository_url']} at "
            f"{upstream['default_branch_commit_at_audit']}"
        )
        return
    result = run_repository_observation(
        repository_url=upstream["repository_url"],
        commit=upstream["default_branch_commit_at_audit"],
        package_id=package_id(manifest),
        run_id=opts.run_id,
        evidence_root=opts.output_directory / "evidence",
        config_path=ROOT / "config" / "audit.yaml",
        manifest_sha256=sha256_file(manifest_path),
        force=opts.force,
    )
    console.print(f"{result.check_id}: {result.status.value}")


@audit_app.command("recipe")
def audit_recipe(ctx: typer.Context, package: Path) -> None:
    opts = options(ctx)
    manifest_path = resolve_manifest(package)
    manifest = load_yaml(manifest_path)
    recipe_test = manifest["recipe_test"]
    if recipe_test["status"] != "reviewed":
        console.print("[yellow]NOT_RUN[/yellow]: recipe test depth has not been reviewed.")
        return
    preserved = opts.output_directory / "work" / package_id(manifest) / "recipe" / "meta.yaml"
    if not preserved.exists():
        raise typer.BadParameter(f"Fetch the pinned recipe first: {preserved}")
    if opts.dry_run:
        console.print(f"Would record reviewed recipe test depth {recipe_test['depth']}")
        return
    result = write_recipe_test_observation(
        package_id=package_id(manifest),
        run_id=opts.run_id,
        recipe_test=recipe_test,
        recipes_commit=manifest["bioconda"]["recipes_commit"],
        recipe_path=manifest["bioconda"]["recipe_path"],
        preserved_recipe=preserved,
        evidence_root=opts.output_directory / "evidence",
        config_path=ROOT / "config" / "rubric.yaml",
        manifest_sha256=sha256_file(manifest_path),
        force=opts.force,
    )
    console.print(f"{result.check_id}: {result.status.value} (depth {recipe_test['depth']})")


@audit_app.command("python")
def audit_python(ctx: typer.Context, package: Path) -> None:
    opts = options(ctx)
    manifest = load_yaml(resolve_manifest(package))
    manifest_path = resolve_manifest(package)
    extracted = opts.output_directory / "work" / package_id(manifest) / "source"
    production_roots = manifest["source_layout"]["production_roots"]
    if not production_roots:
        raise typer.BadParameter("Manifest has no reviewed production source root.")
    source_roots = [extracted / root for root in production_roots]
    missing_roots = [root for root in source_roots if not root.exists()]
    if missing_roots:
        raise typer.BadParameter(
            "Fetch packaged release source first; missing: "
            + ", ".join(str(root) for root in missing_roots)
        )
    if opts.dry_run:
        console.print(f"Would run the fixed Python toolchain against {len(source_roots)} roots")
        return
    results = run_python_analyzers(
        source_roots=source_roots,
        package_id=package_id(manifest),
        run_id=opts.run_id,
        evidence_root=opts.output_directory / "evidence",
        config_root=ROOT / "config",
        manifest_sha256=sha256_file(manifest_path),
        force=opts.force,
    )
    table = Table("Check", "Status", "Observation count")
    for result in results:
        count = next(
            (
                value
                for key, value in result.observed.items()
                if key.endswith("_count") and isinstance(value, int)
            ),
            "-",
        )
        table.add_row(result.check_id, result.status.value, str(count))
    console.print(table)


@audit_app.command("install")
def audit_install(ctx: typer.Context, package: Path) -> None:
    opts = options(ctx)
    manifest_path = resolve_manifest(package)
    manifest = load_yaml(manifest_path)
    executable = manifest["bioconda"]["primary_executables"][0]
    version = str(manifest["bioconda"]["version"])
    if manifest["runtime"]["backend"] == "pixi":
        environment = package_pixi_environment(manifest, opts)
        execute_pixi_probes(
            [
                pixi_probe(
                    manifest,
                    environment,
                    check_id="PKG-IDENTITY-001",
                    domain="package",
                    command=[executable, "--version"],
                    allowed_exit_codes=[0],
                    expected_stdout_contains=version,
                    manifest_path=manifest_path,
                )
            ],
            opts,
        )
        return
    execute_container_probes(
        [
            container_probe(
                manifest,
                check_id="PKG-IDENTITY-001",
                domain="package",
                command=[executable, "--version"],
                allowed_exit_codes=[0],
                expected_stdout_contains=version,
                manifest_path=manifest_path,
            )
        ],
        opts,
    )


@audit_app.command("functional")
def audit_functional(ctx: typer.Context, package: Path) -> None:
    opts = options(ctx)
    manifest_path = resolve_manifest(package)
    manifest = load_yaml(manifest_path)
    functional = manifest["functional_test"]
    if functional["status"] != "reviewed" or functional["command"] is None:
        console.print("[yellow]NOT_RUN[/yellow]: functional test has not been reviewed.")
        return
    fixture = Path(functional["fixture_directory"])
    if not fixture.is_absolute():
        fixture = ROOT / fixture
    if manifest["runtime"]["backend"] == "pixi":
        environment = package_pixi_environment(manifest, opts)
        execute_pixi_probes(
            [
                pixi_probe(
                    manifest,
                    environment,
                    check_id="CLI-FUNCTIONAL-001",
                    domain="functional",
                    command=functional["command"],
                    allowed_exit_codes=[0],
                    fixture_directory=fixture,
                    expected_output_sha256=functional["expected_output_sha256"],
                    manifest_path=manifest_path,
                )
            ],
            opts,
        )
        return
    execute_container_probes(
        [
            container_probe(
                manifest,
                check_id="CLI-FUNCTIONAL-001",
                domain="functional",
                command=functional["command"],
                allowed_exit_codes=[0],
                fixture_directory=fixture,
                expected_output_sha256=functional["expected_output_sha256"],
                manifest_path=manifest_path,
            )
        ],
        opts,
    )


@audit_app.command("all")
def audit_all(ctx: typer.Context, package: Path) -> None:
    audit_recipe(ctx, package)
    audit_install(ctx, package)
    audit_cli(ctx, package)
    audit_functional(ctx, package)
    audit_python(ctx, package)
    audit_repository(ctx, package)


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
    global_json, global_csv = rebuild_global_results(opts.output_directory / "results")
    console.print(f"Updated global table: {global_json} and {global_csv}")


@results_app.command("rebuild-global")
def results_rebuild_global(ctx: typer.Context) -> None:
    """Rebuild the global check fact table from all normalized runs."""
    opts = options(ctx)
    if opts.dry_run:
        console.print("Would rebuild the global table from normalized runs")
        return
    json_path, csv_path = rebuild_global_results(opts.output_directory / "results")
    console.print(f"Wrote {json_path} and {csv_path}")


@report_app.command("build")
def report_build(ctx: typer.Context) -> None:
    opts = options(ctx)
    source = opts.output_directory / "results" / "global" / "check-results.json"
    target = ROOT / "web" / "public" / "data" / "checks.json"
    if not source.exists():
        raise typer.BadParameter(f"Normalize a run or rebuild the global table first: {source}")
    if not opts.dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        rows = json.loads(source.read_text(encoding="utf-8"))
        runs_by_package: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            runs_by_package.setdefault(row["package_id"], []).append(row)
        packages: list[dict[str, Any]] = []
        for manifest_path in sorted((ROOT / "manifests" / "packages").glob("*.yaml")):
            manifest = load_yaml(manifest_path)
            identifier = package_id(manifest)
            package_rows = runs_by_package.get(identifier)
            if not package_rows:
                continue
            latest = max(package_rows, key=lambda row: row["started_at"])
            run_id = latest["run_id"]
            packages.append(
                {
                    "package_id": identifier,
                    "name": manifest["package"]["name"],
                    "version": manifest["bioconda"]["version"],
                    "build": manifest["bioconda"]["build"],
                    "subdir": manifest["bioconda"]["subdir"],
                    "category": manifest["classification"]["tool_category"],
                    "description": manifest["classification"]["notes"],
                    "upstream_url": manifest["upstream"]["repository_url"],
                    "run_id": run_id,
                }
            )
        package_target = target.parent / "packages.json"
        package_target.write_text(json.dumps(packages, indent=2) + "\n", encoding="utf-8")
        award_config = load_award_config(ROOT / "config" / "awards.yaml")
        rankings = rank_packages(packages, rows, award_config)
        ranking_target = target.parent / "rankings.json"
        ranking_target.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "rubric_version": award_config["version"],
                    "title": award_config["title"],
                    "scope_note": award_config["scope_note"],
                    "rankings": rankings,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        write_badges(rankings, ROOT / "web" / "public" / "badges")
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
