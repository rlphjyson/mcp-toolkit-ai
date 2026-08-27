import httpx
import pytest

from api_contract.openapi_loader import list_endpoints, load_spec, resolve_schema

SPEC_YAML = """
openapi: "3.0.0"
info:
  title: "Sample API"
  version: "1.0.0"
paths:
  /users:
    get:
      operationId: listUsers
      responses:
        "200":
          description: OK
  /users/{id}:
    get:
      operationId: getUser
      responses:
        "200":
          description: OK
    delete:
      operationId: deleteUser
      deprecated: true
      responses:
        "200":
          description: OK
components:
  schemas:
    User:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        email:
          type: string
"""


def test_load_spec_from_local_file(tmp_path):
    spec_file = tmp_path / "openapi.yaml"
    spec_file.write_text(SPEC_YAML)

    spec = load_spec(str(spec_file))

    assert spec["info"]["title"] == "Sample API"


def test_load_spec_rejects_non_openapi_content(tmp_path):
    spec_file = tmp_path / "not_a_spec.yaml"
    spec_file.write_text("foo: bar\n")

    with pytest.raises(ValueError, match="does not look like an OpenAPI"):
        load_spec(str(spec_file))


def test_load_spec_from_url_fetches_and_parses(monkeypatch):
    def fake_get(url, timeout=None):
        return httpx.Response(200, text=SPEC_YAML, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    spec = load_spec("https://example.com/openapi.yaml")

    assert spec["info"]["version"] == "1.0.0"


def test_load_spec_from_url_raises_on_http_error(monkeypatch):
    def fake_get(url, timeout=None):
        return httpx.Response(404, text="not found", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(httpx.HTTPStatusError):
        load_spec("https://example.com/openapi.yaml")


def test_list_endpoints_flattens_paths_and_methods():
    import yaml

    spec = yaml.safe_load(SPEC_YAML)

    endpoints = list_endpoints(spec)

    by_path_method = {(e["path"], e["method"]): e for e in endpoints}
    assert by_path_method[("/users", "GET")]["operation_id"] == "listUsers"
    assert by_path_method[("/users/{id}", "DELETE")]["deprecated"] is True
    assert by_path_method[("/users/{id}", "GET")]["deprecated"] is False


def test_resolve_schema_returns_the_named_schema():
    import yaml

    spec = yaml.safe_load(SPEC_YAML)

    schema = resolve_schema(spec, "User")

    assert set(schema["properties"]) == {"id", "name", "email"}


def test_resolve_schema_raises_for_unknown_schema_name():
    import yaml

    spec = yaml.safe_load(SPEC_YAML)

    with pytest.raises(ValueError, match="not found"):
        resolve_schema(spec, "DoesNotExist")
