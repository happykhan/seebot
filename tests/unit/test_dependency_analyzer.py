import pytest

from seebot.analyzers.dependencies import _parse, _parse_cpan_audit
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
