"""Pinned Linux environment for cross-language source analyzers."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from seebot.evidence import sha256_file
from seebot.runtime.pixi import PIXI_IMAGE, _docker_base, _run

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

    @property
    def environment_id(self) -> str:
        profile = "\n".join(
            f"{row.get('name')}={row.get('requested_version')}"
            for row in sorted(self.records, key=lambda row: str(row.get("name")))
        )
        profile_hash = hashlib.sha256(profile.encode()).hexdigest()
        return (
            f"{self.profile}:{sha256_file(self.lock_path)};profile:{profile_hash};"
            f"image:{PIXI_IMAGE.rsplit('@', 1)[-1]}"
        )


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
    command = _docker_base(network="bridge", read_only=False)
    command.extend(
        [
            "--volume",
            f"{root.resolve()}:/workspace:rw",
            "--volume",
            f"{cache_root.resolve()}:/cache:rw",
            "--env",
            "PIXI_CACHE_DIR=/cache",
            "--workdir",
            "/workspace",
            PIXI_IMAGE,
            "pixi",
            "install",
            "--manifest-path",
            "/workspace/pixi.toml",
        ]
    )
    if lock.exists():
        command.append("--locked")
    installed = _run(command)
    if installed.returncode != 0:
        raise RuntimeError(installed.stderr.decode(errors="replace")[-3000:])
    missing_perl_bins = [
        name for name in required_perl_bins if not (root / "perl5/bin" / name).exists()
    ]
    if missing_perl_bins:
        cpan = _docker_base(network="bridge", read_only=False)
        cpan.extend(
            [
                "--volume",
                f"{root.resolve()}:/workspace:rw",
                "--volume",
                f"{cache_root.resolve()}:/cache:rw",
                "--env",
                "PIXI_CACHE_DIR=/cache",
                "--workdir",
                "/workspace",
                PIXI_IMAGE,
                "pixi",
                "run",
                "--frozen",
                "--manifest-path",
                "/workspace/pixi.toml",
                "--",
                "sh",
                "-lc",
                (
                    "ln -sf /workspace/.pixi/envs/default/bin/"
                    "x86_64-conda-linux-gnu-gcc /bin/x86_64-conda-linux-gnu-gcc && "
                    "ln -sfn /workspace/.pixi/envs/default/x86_64-conda-linux-gnu "
                    "/x86_64-conda-linux-gnu && "
                    "cpanm --notest --local-lib-contained /workspace/perl5 "
                    + " ".join(perl_modules)
                ),
            ]
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
    command = _docker_base(network=network, read_only=True)
    command.extend(["--volume", f"{environment_root.resolve()}:/workspace:rw"])
    if source is not None:
        command.extend(["--volume", f"{source.resolve()}:/source:ro", "--workdir", "/source"])
    if work is not None:
        command.extend(["--volume", f"{work.resolve()}:/work:rw"])
    if config is not None:
        command.extend(["--volume", f"{config.resolve()}:/config:ro"])
    command.extend(
        [
            "--env",
            "PERL5LIB=/workspace/perl5/lib/perl5",
            PIXI_IMAGE,
            "pixi",
            "run",
            "--frozen",
            "--manifest-path",
            "/workspace/pixi.toml",
            "--",
            *tool_command,
        ]
    )
    return _run(command, timeout=timeout)
