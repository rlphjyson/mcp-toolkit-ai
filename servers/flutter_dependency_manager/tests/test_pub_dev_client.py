import httpx
import pytest

from flutter_dependency_manager.pub_dev_client import (
    FakePubDevClient,
    RealPubDevClient,
    _is_outdated,
)


@pytest.mark.parametrize(
    ("current_constraint", "latest_version", "expected"),
    [
        ("^1.2.0", "1.2.0", False),
        ("^1.2.0", "1.3.0", True),
        (">=1.0.0 <2.0.0", "1.5.0", True),
        ("~2.0.0", "2.0.0", False),
        ("6.0.0", "6.1.2", True),
        ("^2.3.0", "2.2.0", False),
        ("any", "9.9.9", False),
        ("git:https://example.com/pkg.git", "1.0.0", False),
        ("path:../local_pkg", "1.0.0", False),
        ("sdk:flutter", "1.0.0", False),
        ("^1.0.0-dev", "1.0.0", False),
        ("not-a-version", "1.0.0", False),
    ],
)
def test_is_outdated(current_constraint, latest_version, expected):
    assert _is_outdated(current_constraint, latest_version) is expected


def test_fake_client_returns_canned_up_to_date_package():
    client = FakePubDevClient()

    info = client.get_package_info("sample_up_to_date_pkg")

    assert info["latest"]["version"] == "2.3.0"
    assert info["isDiscontinued"] is False


def test_fake_client_returns_canned_discontinued_package():
    client = FakePubDevClient()

    info = client.get_package_info("sample_discontinued_pkg")

    assert info["isDiscontinued"] is True
    assert info["replacedBy"] == "sample_replacement_pkg"


def test_fake_client_unknown_package_raises_value_error():
    client = FakePubDevClient()

    with pytest.raises(ValueError, match="Unknown pub.dev package"):
        client.get_package_info("totally_unknown_pkg")


def _handler(response_map):
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key not in response_map:
            raise AssertionError(f"Unexpected request: {key}")
        status, payload = response_map[key]
        return httpx.Response(status, json=payload, request=request)

    return handler


def test_real_client_builds_expected_url_and_parses_json():
    payload = {
        "name": "http",
        "latest": {"version": "1.2.0", "pubspec": {"name": "http", "version": "1.2.0"}},
        "isDiscontinued": False,
        "replacedBy": None,
    }
    transport = httpx.MockTransport(_handler({("GET", "/api/packages/http"): (200, payload)}))
    client = RealPubDevClient(transport=transport)

    info = client.get_package_info("http")

    assert info["latest"]["version"] == "1.2.0"


def test_real_client_raises_http_status_error_for_unknown_package():
    transport = httpx.MockTransport(
        _handler({("GET", "/api/packages/nope"): (404, {"error": {"message": "not found"}})})
    )
    client = RealPubDevClient(transport=transport)

    with pytest.raises(httpx.HTTPStatusError):
        client.get_package_info("nope")
