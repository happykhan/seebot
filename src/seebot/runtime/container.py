"""Runtime abstraction for native Pixi, Docker, and Apptainer execution."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from seebot.runtime.pixi_image import PIXI_IMAGE


def runtime_name() -> str:
    requested = os.environ.get("SEEBOT_CONTAINER_RUNTIME")
    if requested:
        if requested not in {"native", "docker", "apptainer"}:
            raise ValueError("SEEBOT_CONTAINER_RUNTIME must be native, docker, or apptainer")
        return requested
    return "docker" if shutil.which("docker") else "apptainer"


def runtime_executable() -> str:
    name = runtime_name()
    executable = (
        os.environ.get("SEEBOT_PIXI_EXECUTABLE") or shutil.which("pixi")
        if name == "native"
        else shutil.which(name)
    )
    if executable is None:
        raise FileNotFoundError(f"{name} is required for canonical Linux x86-64 probes")
    return executable


def image_reference(image: str = PIXI_IMAGE) -> str:
    if runtime_name() == "docker":
        return image
    configured = os.environ.get("SEEBOT_APPTAINER_IMAGE")
    if not configured:
        raise RuntimeError("SEEBOT_APPTAINER_IMAGE must name the prepared Pixi SIF")
    path = Path(configured).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Prepared Apptainer image does not exist: {path}")
    return str(path)


def container_command(
    argv: list[str],
    *,
    image: str = PIXI_IMAGE,
    network: str = "none",
    read_only: bool = True,
    mounts: tuple[tuple[Path, str, str], ...] = (),
    environment: dict[str, str] | None = None,
    workdir: str | None = None,
    interactive: bool = False,
    name: str | None = None,
) -> list[str]:
    """Build one equivalent native, Docker, or Apptainer invocation."""
    executable = runtime_executable()
    if runtime_name() == "native":
        mount_map = {target: str(host.resolve()) for host, target, _ in mounts}
        mount_pattern = re.compile(
            "(?:"
            + "|".join(re.escape(target) for target in sorted(mount_map, key=len, reverse=True))
            + r")(?=/|$)"
        )

        def translate(value: str) -> str:
            if not mount_map:
                return value
            return mount_pattern.sub(lambda match: mount_map[match.group(0)], value)

        translated = [translate(value) for value in argv]
        if translated and translated[0] == "pixi":
            translated[0] = executable
        native_environment = [
            f"{key}={translate(value)}" for key, value in sorted((environment or {}).items())
        ]
        cwd = translate(workdir) if workdir else "/"
        limit = "ulimit -u 256; " if read_only else ""
        return [
            "env",
            *native_environment,
            "bash",
            "-c",
            f'cd "$1"; shift; {limit}exec "$@"',
            "seebot",
            cwd,
            *translated,
        ]
    if runtime_name() == "docker":
        command = [
            executable,
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--cpus",
            "2",
            "--memory",
            "8g",
            "--pids-limit",
            "256",
            "--network",
            network,
        ]
        if read_only:
            command.extend(
                [
                    "--read-only",
                    "--tmpfs",
                    "/tmp:rw,nosuid,size=256m",
                    "--tmpfs",
                    "/run:rw,nosuid,size=16m",
                ]
            )
        if name:
            command.extend(["--name", name])
        for host, target, mode in mounts:
            command.extend(["--volume", f"{host.resolve()}:{target}:{mode}"])
        if interactive:
            command.append("--interactive")
        for key, value in sorted((environment or {}).items()):
            command.extend(["--env", f"{key}={value}"])
        if workdir:
            command.extend(["--workdir", workdir])
        return [*command, image_reference(image), *argv]

    command = [executable, "exec", "--cleanenv", "--containall", "--no-home"]
    if network == "none":
        command.extend(["--net", "--network", "none"])
    for host, target, mode in mounts:
        command.extend(["--bind", f"{host.resolve()}:{target}:{mode}"])
    for key, value in sorted((environment or {}).items()):
        command.extend(["--env", f"{key}={value}"])
    if workdir:
        command.extend(["--pwd", workdir])
    command_argv = (
        ["bash", "-c", 'ulimit -u 256; exec "$@"', "seebot", *argv] if read_only else argv
    )
    return [*command, image_reference(image), *command_argv]


def cleanup_timed_out_container(name: str) -> None:
    """Remove a named Docker container; Apptainer has no persistent container object."""
    if runtime_name() == "docker":
        import subprocess

        subprocess.run(
            [runtime_executable(), "rm", "--force", name], capture_output=True, check=False
        )
