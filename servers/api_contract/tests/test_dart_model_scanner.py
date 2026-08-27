from api_contract.dart_model_scanner import find_dart_model_fields

PLAIN_MODEL = """
class User {
  final String id;
  final String name;
  final String? email;

  User({required this.id, required this.name, this.email});
}
"""

FREEZED_MODEL = """
@freezed
class Product with _$Product {
  const factory Product({
    required String id,
    required String title,
    double? price,
  }) = _Product;
}
"""


def test_finds_fields_in_a_plain_dart_data_class(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "user.dart").write_text(PLAIN_MODEL)

    fields = find_dart_model_fields(tmp_path, "User")

    assert fields == ["email", "id", "name"]


def test_falls_back_to_model_suffix(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "user_model.dart").write_text(PLAIN_MODEL.replace("class User", "class UserModel"))

    fields = find_dart_model_fields(tmp_path, "User")

    assert fields == ["email", "id", "name"]


def test_returns_none_when_no_matching_class_exists(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "user.dart").write_text(PLAIN_MODEL)

    assert find_dart_model_fields(tmp_path, "Order") is None


def test_finds_fields_declared_via_this_constructor_params_without_final(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "point.dart").write_text(
        """
        class Point {
          Point(this.x, this.y);
          final int x;
          final int y;
        }
        """
    )

    fields = find_dart_model_fields(tmp_path, "Point")

    assert fields == ["x", "y"]


def test_finds_fields_in_a_freezed_style_factory_class(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "product.dart").write_text(FREEZED_MODEL)

    fields = find_dart_model_fields(tmp_path, "Product")

    assert fields == ["id", "price", "title"]


def test_scans_nested_lib_directories(tmp_path):
    nested = tmp_path / "lib" / "models" / "nested"
    nested.mkdir(parents=True)
    (nested / "user.dart").write_text(PLAIN_MODEL)

    fields = find_dart_model_fields(tmp_path, "User")

    assert fields == ["email", "id", "name"]
