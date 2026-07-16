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
