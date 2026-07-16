import json
from pathlib import Path

import pytest

from seebot.runtime.assessment import declared_command_names, verify_installed_interface
from seebot.runtime.pixi import PixiEnvironment, command_is_installed, package_executables


def installed_pasta(tmp_path: Path) -> PixiEnvironment:
    root = tmp_path / "pasta"
    prefix = root / ".pixi" / "envs" / "default"
    bindir = prefix / "bin"
    metadata = prefix / "conda-meta"
    bindir.mkdir(parents=True)
    metadata.mkdir()
    executable = bindir / "run_pasta.py"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    record = {"name": "pasta", "version": "1.9.3", "build": "py_0"}
    (metadata / "pasta-1.9.3-py_0.json").write_text(
        json.dumps({**record, "files": ["bin/run_pasta.py", "share/pasta/data.txt"]}),
        encoding="utf-8",
    )
    manifest_path = root / "pixi.toml"
    lock_path = root / "pixi.lock"
    manifest_path.write_text("[workspace]\n", encoding="utf-8")
    lock_path.write_text("locked\n", encoding="utf-8")
    return PixiEnvironment(
        project_id="pasta",
        installation_id="pixi:pasta=1.9.3:py_0",
        root=root,
        manifest_path=manifest_path,
        lock_path=lock_path,
        package_record=record,
    )


def manifest(primary: str) -> dict:
    return {
        "project": {"id": "pasta"},
        "interfaces": {
            "primary": primary,
            "help_commands": [[primary, "--help"]],
            "version_commands": [[primary, "--version"]],
        },
        "valid_run": {"command": None},
        "streams": {"command": None},
        "robustness": {},
    }


def test_preflight_accepts_a_package_owned_primary_command(tmp_path: Path) -> None:
    environment = installed_pasta(tmp_path)

    assert package_executables(environment) == ("run_pasta.py",)
    assert command_is_installed(environment, "run_pasta.py")
    assert declared_command_names(manifest("run_pasta.py")) == ("run_pasta.py",)
    assert verify_installed_interface(manifest("run_pasta.py"), environment) == ("run_pasta.py",)


def test_preflight_rejects_wrong_primary_and_suggests_package_candidates(
    tmp_path: Path,
) -> None:
    environment = installed_pasta(tmp_path)

    with pytest.raises(ValueError, match="primary command 'pasta'.*run_pasta.py"):
        verify_installed_interface(manifest("pasta"), environment)
