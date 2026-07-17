import subprocess
from pathlib import Path

import pytest

from seebot.manifests import load_yaml
from seebot.models import Status
from seebot.runtime import container
from seebot.runtime import pixi as pixi_runtime
from seebot.runtime.assessment import clear_forced_usage_evidence, plan_usage_probes
from seebot.runtime.pixi import (
    ExpectedOutput,
    PixiEnvironment,
    PixiProbeSpec,
    _crash_detected,
    _executable_launch_failed,
    _inspect_output,
    _repair_case_colliding_aliases,
    _restore_fixture_tree_permissions,
    _run,
    _set_fixture_tree_read_only,
    run_pixi_probe,
)


def test_run_delivers_declared_standard_input() -> None:
    completed = _run(
        ["bash", "-c", "read -r value; printf '%s' \"$value\""],
        stdin_bytes=b"fixture-input\n",
    )

    assert completed.returncode == 0
    assert completed.stdout == b"fixture-input"


def test_native_fixture_copy_can_enforce_and_restore_read_only_output(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    nested = fixture / "nested"
    nested.mkdir(parents=True)
    (nested / "input.txt").write_text("input\n", encoding="utf-8")

    _set_fixture_tree_read_only(fixture)
    attempted = _run(["bash", "-c", 'printf output > "$1"', "seebot", fixture / "out.txt"])

    assert attempted.returncode != 0
    assert not (fixture / "out.txt").exists()
    _restore_fixture_tree_permissions(fixture)
    (fixture / "out.txt").write_text("output\n", encoding="utf-8")


def test_output_permission_error_is_not_an_executable_launch_failure() -> None:
    assert not _executable_launch_failed(1, "output.vcf: Permission denied")
    assert _executable_launch_failed(1, "tool: command not found")
    assert _executable_launch_failed(126, "tool: Permission denied")


def test_no_argument_usage_error_accepts_nonstandard_nonzero_exit_codes(tmp_path: Path) -> None:
    environment = PixiEnvironment(
        project_id="primer3",
        installation_id="pixi:primer3=2.6.1=test",
        root=tmp_path,
        manifest_path=tmp_path / "pixi.toml",
        lock_path=tmp_path / "pixi.lock",
        package_record={"name": "primer3", "version": "2.6.1", "build": "test"},
    )
    specs = plan_usage_probes(
        load_yaml(Path("manifests/packages/primer3.yaml")),
        environment,
        fixture_directory=Path("fixtures"),
        manifest_sha256="0" * 64,
    )
    noargs = next(spec for spec in specs if spec.check_id == "CLI-NOARGS-001")

    assert 253 in noargs.allowed_exit_codes
    assert 255 in noargs.allowed_exit_codes
    assert 127 not in noargs.allowed_exit_codes


def test_java_runtime_warning_is_not_misclassified_as_a_crash() -> None:
    warning = "WARNING: java.lang.System::load has been called by a native library"
    assert not _crash_detected(warning)
    assert _crash_detected('Exception in thread "main" java.lang.IllegalStateException: bad')


def test_forced_usage_rerun_removes_only_selected_check_evidence(tmp_path: Path) -> None:
    project = tmp_path / "evidence" / "current" / "tool"
    stale_help = project / "CLI-HELP-001" / "old-probe" / "result.json"
    stale_robustness = project / "CLI-MISSING-INPUT-001" / "old-probe" / "result.json"
    stale_dated_help = project / "2026-07-01" / "CLI-HELP-001" / "old-probe" / "result.json"
    preserved_source = project / "SRC-INVENTORY-001" / "source" / "result.json"
    for path in (stale_help, stale_robustness, stale_dated_help, preserved_source):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")

    clear_forced_usage_evidence(tmp_path, "current", "tool", {"usage"})

    assert not stale_help.exists()
    assert not stale_dated_help.exists()
    assert stale_robustness.exists()
    assert preserved_source.exists()


def test_empty_biological_outputs_are_validated_with_zero_record_cardinality(
    tmp_path: Path,
) -> None:
    fastq = tmp_path / "empty.fastq"
    fastq.write_bytes(b"")
    sam = tmp_path / "header-only.sam"
    sam.write_text("@HD\tVN:1.6\tSO:unknown\n@SQ\tSN:ref\tLN:10\n", encoding="utf-8")

    assert _inspect_output(fastq, "fastq", allow_empty=True) == (True, 0, None)
    assert _inspect_output(sam, "sam", allow_empty=True) == (True, 0, None)
    assert _inspect_output(fastq, "fastq", allow_empty=False)[0] is False


def test_semantically_empty_probe_accepts_created_valid_zero_record_output(
    tmp_path: Path, monkeypatch
) -> None:
    environment_root = tmp_path / "environment"
    environment_root.mkdir()
    manifest_path = environment_root / "pixi.toml"
    lock_path = environment_root / "pixi.lock"
    manifest_path.write_text("[workspace]\n", encoding="utf-8")
    lock_path.write_text("locked\n", encoding="utf-8")
    fixture = tmp_path / "fixtures"
    fixture.mkdir()
    (fixture / "empty.fastq").write_bytes(b"")
    environment = PixiEnvironment(
        project_id="fixture-tool",
        installation_id="pixi:fixture-tool=1.0=test_0",
        root=environment_root,
        manifest_path=manifest_path,
        lock_path=lock_path,
        package_record={"name": "fixture-tool", "version": "1.0", "build": "test_0"},
    )

    def fake_run(
        command: list[str], *, timeout: int = 1800, stdin_bytes: bytes | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        work_mount = next(value for value in command if value.endswith(":/work:rw")).removesuffix(
            ":/work:rw"
        )
        Path(work_mount, "output.fastq").write_bytes(b"")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(pixi_runtime, "_run", fake_run)
    monkeypatch.setenv("SEEBOT_CONTAINER_RUNTIME", "docker")
    monkeypatch.setattr(container.shutil, "which", lambda name: f"/usr/bin/{name}")
    result = run_pixi_probe(
        PixiProbeSpec(
            project_id="fixture-tool",
            check_id="CLI-SEMANTICALLY-EMPTY-INPUT-001",
            probe_id="semantic-empty:fixture-tool",
            domain="robustness",
            command=["fixture-tool", "/fixtures/empty.fastq", "/work/output.fastq"],
            timeout_seconds=10,
            environment=environment,
            executable_id="fixture-tool",
            fixture_directory=fixture,
            expected_outputs=(
                ExpectedOutput("output.fastq", nonempty=False, parser="fastq", record_count=0),
            ),
        ),
        run_id="current",
        evidence_root=tmp_path / "evidence",
        config_path=Path("config/rubric.yaml"),
    )

    assert result.status is Status.PASS
    assert result.observed["outputs"][0]["record_count"] == 0


def test_case_colliding_identical_package_aliases_are_pruned(tmp_path: Path) -> None:
    info = tmp_path / "pkgs" / "fasttree-1" / "info"
    info.mkdir(parents=True)
    (info / "paths.json").write_text(
        '{"paths": ['
        '{"_path": "bin/FastTree", "sha256": "same"},'
        '{"_path": "bin/fasttree", "sha256": "same"},'
        '{"_path": "bin/FastTreeMP", "sha256": "different"}'
        "]}\n",
        encoding="utf-8",
    )
    (info / "files").write_text("bin/FastTree\nbin/fasttree\nbin/FastTreeMP\n", encoding="utf-8")

    adjusted = _repair_case_colliding_aliases(tmp_path)

    assert adjusted == ("fasttree-1:removed-identical-aliases:bin/FastTree",)
    assert "bin/FastTree\n" not in (info / "files").read_text(encoding="utf-8")
    assert "bin/fasttree\n" in (info / "files").read_text(encoding="utf-8")


def test_pixi_probe_uses_bounded_amd64_container_and_validates_output(
    tmp_path: Path, monkeypatch
) -> None:
    environment_root = tmp_path / "environment"
    environment_root.mkdir()
    manifest_path = environment_root / "pixi.toml"
    lock_path = environment_root / "pixi.lock"
    manifest_path.write_text("[workspace]\n", encoding="utf-8")
    lock_path.write_text("locked\n", encoding="utf-8")
    fixture = tmp_path / "fixtures"
    fixture.mkdir()
    (fixture / "input.fastq").write_text("@r1\nACGT\n+\nIIII\n", encoding="utf-8")
    environment = PixiEnvironment(
        project_id="fixture-tool",
        installation_id="pixi:fixture-tool=1.0=test_0",
        root=environment_root,
        manifest_path=manifest_path,
        lock_path=lock_path,
        package_record={"name": "fixture-tool", "version": "1.0", "build": "test_0"},
    )

    recorded: list[str] = []

    def fake_run(
        command: list[str], *, timeout: int = 1800, stdin_bytes: bytes | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        recorded.extend(command)
        work_mount = next(value for value in command if value.endswith(":/work:rw")).removesuffix(
            ":/work:rw"
        )
        Path(work_mount, "output.fastq").write_text("@r1\nACGT\n+\nIIII\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, b"complete\n", b"")

    monkeypatch.setattr(pixi_runtime, "_run", fake_run)
    monkeypatch.setenv("SEEBOT_CONTAINER_RUNTIME", "docker")
    monkeypatch.setattr(container.shutil, "which", lambda name: f"/usr/bin/{name}")
    spec = PixiProbeSpec(
        project_id="fixture-tool",
        check_id="CLI-VALID-RUN-001",
        probe_id="cli-valid-run-001:fixture-tool",
        domain="usage",
        command=["fixture-tool", "/fixtures/input.fastq", "/work/output.fastq"],
        timeout_seconds=10,
        environment=environment,
        executable_id="fixture-tool",
        fixture_directory=fixture,
        expected_outputs=(ExpectedOutput("output.fastq", parser="fastq"),),
    )

    result = run_pixi_probe(
        spec,
        run_id="current",
        evidence_root=tmp_path / "evidence",
        config_path=Path("config/rubric.yaml"),
    )

    assert result.status is Status.PASS
    assert result.observed["outputs"][0]["structurally_valid"] is True
    assert "linux/amd64" in recorded
    assert "none" in recorded
    assert "--cpus" in recorded
    assert "--memory" in recorded
    assert result.environment_id.startswith("pixi-lock:")


def test_timeout_is_untestable_not_project_failure(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "environment"
    root.mkdir()
    (root / "pixi.toml").write_text("[workspace]\n", encoding="utf-8")
    (root / "pixi.lock").write_text("locked\n", encoding="utf-8")
    environment = PixiEnvironment(
        project_id="slow-tool",
        installation_id="pixi:slow-tool=1.0=0",
        root=root,
        manifest_path=root / "pixi.toml",
        lock_path=root / "pixi.lock",
        package_record={"name": "slow-tool", "version": "1.0", "build": "0"},
    )

    def timeout(
        command: list[str], *, timeout: int = 1800, stdin_bytes: bytes | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(pixi_runtime, "_run", timeout)
    monkeypatch.setenv("SEEBOT_CONTAINER_RUNTIME", "docker")
    monkeypatch.setattr(container.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    result = run_pixi_probe(
        PixiProbeSpec(
            project_id="slow-tool",
            check_id="CLI-VALID-RUN-001",
            probe_id="cli-valid-run-001:slow-tool",
            domain="usage",
            command=["slow-tool"],
            timeout_seconds=1,
            environment=environment,
        ),
        run_id="current",
        evidence_root=tmp_path / "evidence",
        config_path=Path("config/rubric.yaml"),
    )
    assert result.status is Status.UNTESTABLE


@pytest.mark.parametrize("exit_code", [1, 127])
def test_missing_executable_is_audit_error_not_graceful_rejection(
    tmp_path: Path, monkeypatch, exit_code: int
) -> None:
    root = tmp_path / "environment"
    root.mkdir()
    (root / "pixi.toml").write_text("[workspace]\n", encoding="utf-8")
    (root / "pixi.lock").write_text("locked\n", encoding="utf-8")
    environment = PixiEnvironment(
        project_id="missing-tool",
        installation_id="pixi:missing-tool=1.0=0",
        root=root,
        manifest_path=root / "pixi.toml",
        lock_path=root / "pixi.lock",
        package_record={"name": "missing-tool", "version": "1.0", "build": "0"},
    )

    monkeypatch.setattr(
        pixi_runtime,
        "_run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command, exit_code, b"", b"missing-tool: command not found\n"
        ),
    )
    monkeypatch.setenv("SEEBOT_CONTAINER_RUNTIME", "docker")
    monkeypatch.setattr(container.shutil, "which", lambda name: f"/usr/bin/{name}")
    result = run_pixi_probe(
        PixiProbeSpec(
            project_id="missing-tool",
            check_id="CLI-MALFORMED-INPUT-001",
            probe_id="malformed:missing-tool",
            domain="robustness",
            command=["missing-tool", "/fixtures/malformed.fasta"],
            timeout_seconds=10,
            environment=environment,
            error_contract=True,
            diagnostic_expectation="specific",
        ),
        run_id="current",
        evidence_root=tmp_path / "evidence",
        config_path=Path("config/rubric.yaml"),
    )

    assert result.status is Status.ERROR
    assert result.observed["audit_error"] == "ExecutableLaunchFailure"
    assert result.notes == (
        "The installed executable could not be launched in the audited environment."
    )


def test_rejection_can_diagnose_on_stdout_and_leave_an_auxiliary_log(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "environment"
    root.mkdir()
    (root / "pixi.toml").write_text("[workspace]\n", encoding="utf-8")
    (root / "pixi.lock").write_text("locked\n", encoding="utf-8")
    environment = PixiEnvironment(
        project_id="stdout-tool",
        installation_id="pixi:stdout-tool=1.0=0",
        root=root,
        manifest_path=root / "pixi.toml",
        lock_path=root / "pixi.lock",
        package_record={"name": "stdout-tool", "version": "1.0", "build": "0"},
    )

    def reject_with_log(command, **_kwargs):
        work_mount = next(value for value in command if value.endswith(":/work:rw"))
        Path(work_mount.removesuffix(":/work:rw"), "run.log").write_text(
            "started\n", encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 255, b"Error: too few sequences\n", b"")

    monkeypatch.setattr(pixi_runtime, "_run", reject_with_log)
    monkeypatch.setenv("SEEBOT_CONTAINER_RUNTIME", "docker")
    monkeypatch.setattr(container.shutil, "which", lambda name: f"/usr/bin/{name}")
    result = run_pixi_probe(
        PixiProbeSpec(
            project_id="stdout-tool",
            check_id="CLI-EMPTY-INPUT-001",
            probe_id="empty:stdout-tool",
            domain="robustness",
            command=["stdout-tool", "/fixtures/empty.fasta"],
            timeout_seconds=10,
            environment=environment,
            error_contract=True,
            diagnostic_expectation="specific_or_generic",
            required_any_text=("too few sequences",),
        ),
        run_id="current",
        evidence_root=tmp_path / "evidence",
        config_path=Path("config/rubric.yaml"),
    )

    assert result.status is Status.PASS
    assert result.observed["diagnostic_class"] == "GENERIC"
    assert result.observed["created_files"] == ["run.log"]


def test_native_probe_copies_fixtures_before_allowing_tool_writes(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "environment"
    root.mkdir()
    (root / "pixi.toml").write_text("[workspace]\n", encoding="utf-8")
    (root / "pixi.lock").write_text("locked\n", encoding="utf-8")
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "input.txt").write_text("input\n", encoding="utf-8")
    environment = PixiEnvironment(
        project_id="writer",
        installation_id="pixi:writer=1.0=0",
        root=root,
        manifest_path=root / "pixi.toml",
        lock_path=root / "pixi.lock",
        package_record={"name": "writer", "version": "1.0", "build": "0"},
    )

    def write_beside_input(command, **_kwargs):
        copied_input = Path(next(value for value in command if value.endswith("input.txt")))
        copied_input.with_name("generated.txt").write_text("output\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, b"ok\n", b"")

    monkeypatch.setattr(pixi_runtime, "_run", write_beside_input)
    monkeypatch.setenv("SEEBOT_CONTAINER_RUNTIME", "native")
    monkeypatch.setenv("SEEBOT_PIXI_EXECUTABLE", "/usr/bin/env")
    result = run_pixi_probe(
        PixiProbeSpec(
            project_id="writer",
            check_id="CLI-VALID-RUN-001",
            probe_id="valid:writer",
            domain="usage",
            command=["writer", "/fixtures/input.txt"],
            timeout_seconds=10,
            environment=environment,
            fixture_directory=fixtures,
        ),
        run_id="current",
        evidence_root=tmp_path / "evidence",
        config_path=Path("config/rubric.yaml"),
    )

    assert not (fixtures / "generated.txt").exists()
    assert result.observed["created_files"] == [".fixture-sandbox/generated.txt"]
