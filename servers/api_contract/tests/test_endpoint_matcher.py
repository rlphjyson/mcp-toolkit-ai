from api_contract.endpoint_matcher import _normalize_path_for_matching, find_called_endpoint_paths


def test_finds_dio_call_literals(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "api.dart").write_text(
        """
        class ApiClient {
          final Dio _dio;
          Future<void> fetchUsers() => _dio.get('/users');
          Future<void> createUser(Map<String, dynamic> body) => _dio.post('/users', data: body);
        }
        """
    )

    paths = find_called_endpoint_paths(tmp_path)

    assert paths == {"/users"}


def test_finds_http_client_call_literals(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "api.dart").write_text(
        """
        void run(http.Client client) {
          client.get(Uri.parse('/status'));
          client.delete('/legacy');
        }
        """
    )

    paths = find_called_endpoint_paths(tmp_path)

    assert paths == {"/legacy"}


def test_ignores_non_path_string_literals(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "api.dart").write_text(
        """
        void run(Dio dio) {
          dio.get('users');
          dio.post('/orders');
        }
        """
    )

    paths = find_called_endpoint_paths(tmp_path)

    assert paths == {"/orders"}


def test_normalizes_openapi_param_segment():
    assert _normalize_path_for_matching("/users/{id}") == "/users/*"


def test_normalizes_dart_bare_interpolation_segment():
    assert _normalize_path_for_matching("/users/$userId") == "/users/*"


def test_normalizes_dart_braced_interpolation_segment():
    assert _normalize_path_for_matching("/users/${user.id}/orders") == "/users/*/orders"


def test_normalized_openapi_and_dart_paths_match():
    spec_path = "/users/{id}"
    called_path = "/users/$userId"

    assert _normalize_path_for_matching(spec_path) == _normalize_path_for_matching(called_path)


def test_paths_with_no_params_normalize_unchanged():
    assert _normalize_path_for_matching("/users") == "/users"
