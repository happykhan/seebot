import hashlib
import sys
from pathlib import Path

from seebot.models import Status
from seebot.runtime import pixi as pixi_runtime
from seebot.runtime.pixi import PixiEnvironment, PixiProbeSpec, run_pixi_probe


def test_pixi_probe_maps_fixtures_and_records_solved_package(tmp_path: Path, monkeypatch) -> None:
    fake_pixi = tmp_path / "pixi"
    fake_pixi.write_text(
        "#!/usr/bin/env python3\n"
        "import subprocess, sys\n"
        "marker = sys.argv.index('--')\n"
        "raise SystemExit(subprocess.run(sys.argv[marker + 1:]).returncode)\n",
        encoding="utf-8",
    )
    fake_pixi.chmod(0o755)
    monkeypatch.setattr(pixi_runtime, "pixi_executable", lambda: fake_pixi)

    environment_root = tmp_path / "environment"
    environment_root.mkdir()
    manifest_path = environment_root / "pixi.toml"
    lock_path = environment_root / "pixi.lock"
    manifest_path.write_text("[workspace]\n", encoding="utf-8")
    lock_path.write_text("locked\n", encoding="utf-8")
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "input.txt").write_text("observed\n", encoding="utf-8")
    expected_hash = hashlib.sha256(b"observed\n").hexdigest()
    environment = PixiEnvironment(
        manifest_path=manifest_path,
        lock_path=lock_path,
        platform="test-platform",
        package_record={
            "name": "fixture-tool",
            "version": "1.0",
            "build": "test_0",
            "subdir": "test-platform",
            "sha256": "a" * 64,
            "url": "https://example.invalid/fixture-tool.conda",
        },
        pixi_version="pixi 1.0",
    )
    spec = PixiProbeSpec(
        package_id="fixture-tool__1.0__test_0__test-platform",
        check_id="CLI-FUNCTIONAL-001",
        domain="functional",
        command=[
            sys.executable,
            "-c",
            "import shutil,sys; shutil.copyfile(sys.argv[1],sys.argv[2])",
            "/fixtures/input.txt",
            "/work/output.txt",
        ],
        allowed_exit_codes=[0],
        timeout_seconds=10,
        environment=environment,
        fixture_directory=fixture,
        expected_output_sha256={"output.txt": expected_hash},
    )

    result = run_pixi_probe(
        spec,
        run_id="pixi-test",
        evidence_root=tmp_path / "evidence",
        config_path=Path("config/rubric.yaml"),
    )

    assert result.status is Status.PASS
    assert result.observed["output_sha256"] == {"output.txt": expected_hash}
    assert result.observed["resolved_package"] == {
        "name": "fixture-tool",
        "version": "1.0",
        "build": "test_0",
        "subdir": "test-platform",
    }
    assert result.environment_id.startswith("pixi-lock:sha256:")
