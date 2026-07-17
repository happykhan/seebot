"""Pinned Linux environment for cross-language source analyzers."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from seebot.evidence import sha256_file
from seebot.runtime.container import container_command, runtime_executable, runtime_name
from seebot.runtime.pixi import _run
from seebot.runtime.pixi_image import PIXI_IMAGE

ANALYZER_MANIFEST = """[workspace]
name = "seebot-source-analyzers"
channels = ["conda-forge", "bioconda"]
platforms = ["linux-64"]

[dependencies]
python = "3.12.*"
ruff = "==0.15.21"
pylint = "==4.0.6"
bandit = "==1.9.4"
vulture = "==2.15"
cppcheck = "==2.21.0"
pmd = "==7.19.0"
cython-lint = "==0.21.0"
rust = "==1.97.0"
cargo-audit = "==0.22.1"
osv-scanner = "==2.4.0"
perl = "5.32.*"
perl-app-cpanminus = "==1.7048"
make = "==4.4.1"
c-compiler = "==1.11.0"
sysroot_linux-64 = "==2.17"
zlib = "==1.3.2"
"""

ANALYZER_VERSIONS = {
    "python": "3.12.*",
    "ruff": "0.15.21",
    "pylint": "4.0.6",
    "bandit": "1.9.4",
    "vulture": "2.15",
    "cppcheck": "2.21.0",
    "pmd": "7.19.0",
    "cython-lint": "0.21.0",
    "rust": "1.97.0",
    "cargo-audit": "0.22.1",
    "osv-scanner": "2.4.0",
    "perl": "5.32.*",
    "Perl::Critic": "1.156",
    "CPAN::Audit": "20260622.001",
    "zlib": "1.3.2",
}

DEPENDENCY_ANALYZER_MANIFEST = """[workspace]
name = "seebot-dependency-analyzers"
channels = ["conda-forge", "bioconda"]
platforms = ["linux-64"]

[dependencies]
osv-scanner = "==2.4.0"
perl = "5.32.*"
perl-app-cpanminus = "==1.7048"
make = "==4.4.1"
c-compiler = "==1.11.0"
sysroot_linux-64 = "==2.17"
zlib = "==1.3.2"
"""

DEPENDENCY_ANALYZER_VERSIONS = {
    "osv-scanner": "2.4.0",
    "perl": "5.32.*",
    "CPAN::Audit": "20260622.001",
    "zlib": "1.3.2",
}


@dataclass(frozen=True)
class AnalyzerEnvironment:
    root: Path
    lock_path: Path
    records: list[dict[str, object]]
    profile: str = "source-analyzers"

    @cached_property
    def environment_id(self) -> str:
        profile = "\n".join(
            f"{row.get('name')}={row.get('requested_version')}"
            for row in sorted(self.records, key=lambda row: str(row.get("name")))
        )
        profile_hash = hashlib.sha256(profile.encode()).hexdigest()
        runtime = (
            f"native-pixi:{sha256_file(Path(runtime_executable()))}"
            if runtime_name() == "native"
            else f"image:{PIXI_IMAGE.rsplit('@', 1)[-1]}"
        )
        return f"{self.profile}:{sha256_file(self.lock_path)};profile:{profile_hash};{runtime}"


def _prepare_environment(
    root: Path,
    cache_root: Path,
    *,
    manifest_text: str,
    versions: dict[str, str],
    profile: str,
    perl_modules: tuple[str, ...],
    required_perl_bins: tuple[str, ...],
) -> AnalyzerEnvironment:
    root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)
    manifest = root / "pixi.toml"
    lock = root / "pixi.lock"
    if not manifest.exists() or manifest.read_text(encoding="utf-8") != manifest_text:
        manifest.write_text(manifest_text, encoding="utf-8")
        lock.unlink(missing_ok=True)
        shutil.rmtree(root / ".pixi", ignore_errors=True)
        shutil.rmtree(root / "perl5", ignore_errors=True)
    offline = os.environ.get("SEEBOT_OFFLINE") == "1"
    command = container_command(
        [
            "pixi",
            "install",
            "--manifest-path",
            "/workspace/pixi.toml",
        ],
        network="none" if offline else "bridge",
        read_only=False,
        mounts=((root, "/workspace", "rw"), (cache_root, "/cache", "rw")),
        environment={"PIXI_CACHE_DIR": "/cache"},
        workdir="/workspace",
    )
    if lock.exists():
        command.append("--locked")
    prepared_prefix = root / ".pixi" / "envs" / "default"
    if offline and (not lock.is_file() or not prepared_prefix.is_dir()):
        raise RuntimeError(f"Offline analyzer environment is incomplete: {root}")
    installed = subprocess.CompletedProcess(command, 0, b"", b"") if offline else _run(command)
    if installed.returncode != 0:
        raise RuntimeError(installed.stderr.decode(errors="replace")[-3000:])
    missing_perl_bins = [
        name for name in required_perl_bins if not (root / "perl5/bin" / name).exists()
    ]
    if missing_perl_bins:
        if offline:
            raise RuntimeError("Prepared analyzer environment is missing required Perl tools")
        install_script = (
            "cpanm --notest --local-lib-contained /workspace/perl5 " + " ".join(perl_modules)
            if runtime_name() == "native"
            else (
                "ln -sf /workspace/.pixi/envs/default/bin/"
                "x86_64-conda-linux-gnu-gcc /bin/x86_64-conda-linux-gnu-gcc && "
                "ln -sfn /workspace/.pixi/envs/default/x86_64-conda-linux-gnu "
                "/x86_64-conda-linux-gnu && "
                "cpanm --notest --local-lib-contained /workspace/perl5 " + " ".join(perl_modules)
            )
        )
        cpan = container_command(
            [
                "pixi",
                "run",
                "--frozen",
                "--manifest-path",
                "/workspace/pixi.toml",
                "--",
                "sh",
                "-lc",
                install_script,
            ],
            network="bridge",
            read_only=False,
            mounts=((root, "/workspace", "rw"), (cache_root, "/cache", "rw")),
            environment={"PIXI_CACHE_DIR": "/cache"},
            workdir="/workspace",
        )
        completed = _run(cpan)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.decode(errors="replace")[-3000:])
    records: list[dict[str, object]] = [
        {"name": name, "requested_version": version} for name, version in versions.items()
    ]
    return AnalyzerEnvironment(root=root, lock_path=lock, records=records, profile=profile)


def prepare_analyzer_environment(root: Path, cache_root: Path) -> AnalyzerEnvironment:
    return _prepare_environment(
        root,
        cache_root,
        manifest_text=ANALYZER_MANIFEST,
        versions=ANALYZER_VERSIONS,
        profile="source-analyzers",
        perl_modules=("Perl::Critic@1.156", "CPAN::Audit@20260622.001"),
        required_perl_bins=("perlcritic", "cpan-audit"),
    )


def prepare_dependency_analyzer_environment(root: Path, cache_root: Path) -> AnalyzerEnvironment:
    """Prepare the smaller scanner profile used by dependency-only reruns."""
    return _prepare_environment(
        root,
        cache_root,
        manifest_text=DEPENDENCY_ANALYZER_MANIFEST,
        versions=DEPENDENCY_ANALYZER_VERSIONS,
        profile="dependency-analyzers",
        perl_modules=("CPAN::Audit@20260622.001",),
        required_perl_bins=("cpan-audit",),
    )


def analyzer_command(
    environment_root: Path,
    tool_command: list[str],
    *,
    source: Path | None = None,
    work: Path | None = None,
    config: Path | None = None,
    network: str = "none",
    timeout: int = 300,
) -> subprocess.CompletedProcess[bytes]:
    mounts: list[tuple[Path, str, str]] = [(environment_root, "/workspace", "rw")]
    if source is not None:
        mounts.append((source, "/source", "ro"))
    if work is not None:
        mounts.append((work, "/work", "rw"))
    if config is not None:
        mounts.append((config, "/config", "ro"))
    command = container_command(
        [
            "pixi",
            "run",
            "--frozen",
            "--manifest-path",
            "/workspace/pixi.toml",
            "--",
            *tool_command,
        ],
        network=network,
        mounts=tuple(mounts),
        environment={"PERL5LIB": "/workspace/perl5/lib/perl5"},
        workdir="/source" if source is not None else None,
    )
    return _run(command, timeout=timeout)
