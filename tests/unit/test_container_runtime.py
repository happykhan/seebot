from pathlib import Path

from seebot.runtime import container


def test_apptainer_command_uses_prepared_sif_and_network_namespace(
    tmp_path: Path, monkeypatch
) -> None:
    image = tmp_path / "pixi.sif"
    image.write_bytes(b"sif")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("SEEBOT_CONTAINER_RUNTIME", "apptainer")
    monkeypatch.setenv("SEEBOT_APPTAINER_IMAGE", str(image))
    monkeypatch.setattr(container.shutil, "which", lambda name: f"/usr/bin/{name}")

    command = container.container_command(
        ["pixi", "--version"],
        mounts=((workspace, "/workspace", "rw"),),
        environment={"PIXI_CACHE_DIR": "/cache"},
        workdir="/workspace",
    )

    assert command[:3] == ["/usr/bin/apptainer", "exec", "--cleanenv"]
    assert "--containall" in command
    assert command[command.index("--network") + 1] == "none"
    assert f"{workspace.resolve()}:/workspace:rw" in command
    assert str(image.resolve()) in command
    assert any("ulimit -u 256" in part for part in command)

    install = container.container_command(["pixi", "install"], read_only=False)
    assert not any("ulimit -u 256" in part for part in install)


def test_native_translation_does_not_rewrite_translated_host_paths(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "current" / "work" / "source-analyzers"
    work = tmp_path / "current" / "evidence" / "current" / "project" / "check"
    source = tmp_path / "scratch" / "checkout"
    workspace.mkdir(parents=True)
    work.mkdir(parents=True)
    source.mkdir(parents=True)
    pixi = tmp_path / "pixi"
    pixi.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("SEEBOT_CONTAINER_RUNTIME", "native")
    monkeypatch.setenv("SEEBOT_PIXI_EXECUTABLE", str(pixi))

    command = container.container_command(
        [
            "pixi",
            "run",
            "--manifest-path",
            "/workspace/pixi.toml",
            "--",
            "cppcheck",
            "/source/tool.c",
            "--file-list=/work/source-files.txt",
        ],
        mounts=((workspace, "/workspace", "rw"), (source, "/source", "ro"), (work, "/work", "rw")),
        environment={"PERL5LIB": "/workspace/perl5/lib/perl5"},
        workdir="/source",
    )

    assert str(workspace / "pixi.toml") in command
    assert f"PERL5LIB={workspace / 'perl5/lib/perl5'}" in command
    assert str(work / str(workspace).lstrip("/")) not in command
    assert f"--file-list={work}/source-files.txt" in command
