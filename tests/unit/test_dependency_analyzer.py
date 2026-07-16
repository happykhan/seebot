import json
import zipfile

import pytest

from seebot.analyzers.dependencies import (
    _parse,
    _parse_cpan_audit,
    discover_installed_ecosystem_packages,
    parse_python_dependency_declarations,
    reachable_conda_packages,
)
from seebot.models import Applicability, Status


def test_dependency_parser_marks_missing_supported_input_not_applicable() -> None:
    observed, status, applicability, notes = _parse({"results": []})
    assert status is Status.NOT_APPLICABLE
    assert applicability is Applicability.NOT_APPLICABLE
    assert observed["advisory_count"] == 0
    assert notes


@pytest.mark.parametrize(
    ("source", "ecosystem"),
    [
        ("requirements.txt", "PyPI"),
        ("package-lock.json", "npm"),
        ("pom.xml", "Maven"),
        ("Cargo.lock", "crates.io"),
        ("conan.lock", "ConanCenter"),
    ],
)
def test_dependency_parser_accepts_osv_results_from_multiple_ecosystems(
    source: str, ecosystem: str
) -> None:
    observed, status, applicability, notes = _parse(
        {
            "results": [
                {
                    "source": {"path": f"/source/{source}", "type": "lockfile"},
                    "packages": [
                        {
                            "package": {
                                "name": "demo",
                                "version": "1.0",
                                "ecosystem": ecosystem,
                            },
                            "vulnerabilities": [],
                        }
                    ],
                }
            ]
        }
    )
    assert status is Status.OBSERVED
    assert applicability is Applicability.APPLICABLE
    assert notes is None
    assert observed["supported_sources"] == [source]
    assert observed["advisory_count"] == 0


def test_dependency_parser_retains_native_advisory_fields() -> None:
    payload = {
        "results": [
            {
                "source": {"path": "/source/Cargo.lock", "type": "lockfile"},
                "packages": [
                    {
                        "package": {"name": "demo", "version": "1.0", "ecosystem": "crates.io"},
                        "vulnerabilities": [
                            {
                                "id": "RUSTSEC-1",
                                "aliases": ["CVE-1"],
                                "severity": [{"type": "CVSS_V3", "score": "7.5"}],
                                "affected": [
                                    {
                                        "ranges": [
                                            {
                                                "events": [
                                                    {"introduced": "0"},
                                                    {"fixed": "1.1"},
                                                ]
                                            }
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    observed, status, applicability, notes = _parse(payload)
    assert status is Status.OBSERVED
    assert applicability is Applicability.APPLICABLE
    assert notes is None
    assert observed["supported_sources"] == ["Cargo.lock"]
    assert observed["advisories"] == [
        {
            "advisory_id": "RUSTSEC-1",
            "aliases": ["CVE-1"],
            "ecosystem": "crates.io",
            "dependency": "demo",
            "resolved_version": "1.0",
            "source": "Cargo.lock",
            "native_severity": ["CVSS_V3:7.5"],
            "fixed_versions": ["1.1"],
        }
    ]


def test_cpan_audit_parser_retains_distribution_and_source() -> None:
    rows = _parse_cpan_audit(
        {
            "dists": {
                "Demo-Dist": {
                    "version": "1.2",
                    "advisories": [{"id": "CPANSA-Demo-2026-01", "cves": ["CVE-2026-1"]}],
                }
            }
        },
        "cpanfile.snapshot",
    )
    assert rows == [
        {
            "advisory_id": "CPANSA-Demo-2026-01",
            "aliases": ["CVE-2026-1"],
            "ecosystem": "CPAN",
            "dependency": "Demo-Dist",
            "resolved_version": "1.2",
            "source": "cpanfile.snapshot",
            "native_severity": [],
            "fixed_versions": [],
        }
    ]


def test_pyproject_dependencies_are_recorded_by_role(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "demo"
dependencies = ["archspec~=0.2.0; python_version >= '3.8'"]

[project.optional-dependencies]
docs = ["sphinx>=8"]

[build-system]
requires = ["hatchling>=1.27", "cython~=3.0"]

[dependency-groups]
dev = ["pytest>=8"]
""",
        encoding="utf-8",
    )

    rows = parse_python_dependency_declarations(tmp_path)

    assert {(row["name"], row["role"]) for row in rows} == {
        ("archspec", "runtime"),
        ("sphinx", "optional"),
        ("hatchling", "build"),
        ("cython", "build"),
        ("pytest", "development"),
    }
    archspec = next(row for row in rows if row["name"] == "archspec")
    assert archspec["specifier"] == "~=0.2.0"
    assert archspec["marker"] == 'python_version >= "3.8"'


def test_conda_inventory_is_restricted_to_the_audited_package_closure() -> None:
    records = [
        {"name": "demo", "version": "1", "depends": ["python >=3.12", "zlib >=1.3"]},
        {"name": "python", "version": "3.12", "depends": ["openssl >=3"]},
        {"name": "zlib", "version": "1.3", "depends": []},
        {"name": "openssl", "version": "3.4", "depends": []},
        {"name": "unrelated", "version": "9", "depends": []},
    ]

    closure = reachable_conda_packages(records, "demo")

    assert [row["name"] for row in closure] == ["demo", "openssl", "python", "zlib"]


def test_installed_inventory_discovers_python_maven_and_npm_metadata(tmp_path) -> None:
    python_metadata = tmp_path / "lib/python3.12/site-packages/archspec-0.2.5.dist-info/METADATA"
    python_metadata.parent.mkdir(parents=True)
    python_metadata.write_text("Name: archspec\nVersion: 0.2.5\n", encoding="utf-8")

    jar = tmp_path / "share/java/demo.jar"
    jar.parent.mkdir(parents=True)
    with zipfile.ZipFile(jar, "w") as archive:
        archive.writestr(
            "META-INF/maven/org.example/demo/pom.properties",
            "groupId=org.example\nartifactId=demo\nversion=1.2.3\n",
        )

    npm_metadata = tmp_path / "lib/node_modules/@scope/demo/package.json"
    npm_metadata.parent.mkdir(parents=True)
    npm_metadata.write_text(
        json.dumps({"name": "@scope/demo", "version": "4.5.6"}), encoding="utf-8"
    )

    packages = discover_installed_ecosystem_packages(tmp_path)

    assert {(row["ecosystem"], row["name"], row["version"]) for row in packages} == {
        ("PyPI", "archspec", "0.2.5"),
        ("Maven", "org.example:demo", "1.2.3"),
        ("npm", "@scope/demo", "4.5.6"),
    }
