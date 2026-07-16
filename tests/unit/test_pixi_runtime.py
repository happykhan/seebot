import subprocess
from pathlib import Path

from seebot.models import Status
from seebot.runtime import container
from seebot.runtime import pixi as pixi_runtime
from seebot.runtime.pixi import (
    ExpectedOutput,
    PixiEnvironment,
    PixiProbeSpec,
    _inspect_output,
    _repair_case_colliding_aliases,
    run_pixi_probe,
)


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


def test_missing_executable_is_audit_error_not_graceful_rejection(
    tmp_path: Path, monkeypatch
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
            command, 127, b"", b"missing-tool: command not found\n"
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
