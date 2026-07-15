from seebot.analyzers.dependencies import _parse
from seebot.models import Applicability, Status


def test_dependency_parser_marks_missing_supported_input_not_applicable() -> None:
    observed, status, applicability, notes = _parse({"results": []})
    assert status is Status.NOT_APPLICABLE
    assert applicability is Applicability.NOT_APPLICABLE
    assert observed["advisory_count"] == 0
    assert notes


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
            "native_severity": ["CVSS_V3:7.5"],
            "fixed_versions": ["1.1"],
        }
    ]
