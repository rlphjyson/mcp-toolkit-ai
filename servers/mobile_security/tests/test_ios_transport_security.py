import plistlib

import pytest

from mobile_security.ios_transport_security import check_ios_transport_security


def _write_plist(project_path, contents):
    runner_dir = project_path / "ios" / "Runner"
    runner_dir.mkdir(parents=True)
    with (runner_dir / "Info.plist").open("wb") as f:
        plistlib.dump(contents, f)


def test_check_ios_transport_security_flags_arbitrary_loads_and_domain_exceptions(tmp_path):
    _write_plist(
        tmp_path,
        {
            "NSAppTransportSecurity": {
                "NSAllowsArbitraryLoads": True,
                "NSExceptionDomains": {
                    "example.com": {"NSExceptionAllowsInsecureHTTPLoads": True},
                    "safe.example.com": {"NSExceptionAllowsInsecureHTTPLoads": False},
                },
            }
        },
    )

    result = check_ios_transport_security(tmp_path)

    assert result["ats_configured"] is True
    assert result["allows_arbitrary_loads"] is True
    assert result["insecure_domain_exceptions"] == ["example.com"]


def test_check_ios_transport_security_reports_unconfigured_ats(tmp_path):
    _write_plist(tmp_path, {"CFBundleName": "Runner"})

    result = check_ios_transport_security(tmp_path)

    assert result == {
        "ats_configured": False,
        "allows_arbitrary_loads": False,
        "insecure_domain_exceptions": [],
    }


def test_check_ios_transport_security_raises_when_plist_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="Info.plist"):
        check_ios_transport_security(tmp_path)
