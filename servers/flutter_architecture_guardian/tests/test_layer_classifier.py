from flutter_architecture_guardian.layer_classifier import classify_clean_layer, classify_feature


def test_classify_clean_layer_finds_presentation():
    assert classify_clean_layer("presentation/home_screen.dart") == "presentation"


def test_classify_clean_layer_finds_domain_nested_under_a_feature():
    assert classify_clean_layer("checkout/domain/entities/cart.dart") == "domain"


def test_classify_clean_layer_finds_data():
    assert classify_clean_layer("data/repository_impl.dart") == "data"


def test_classify_clean_layer_returns_none_for_unmatched():
    assert classify_clean_layer("main.dart") is None


def test_classify_feature_finds_feature_name():
    assert classify_feature("features/checkout/cart_screen.dart") == "checkout"


def test_classify_feature_returns_core_for_core_dir():
    assert classify_feature("core/widgets/button.dart") == "core"


def test_classify_feature_returns_core_for_shared_dir():
    assert classify_feature("shared/utils.dart") == "core"


def test_classify_feature_returns_none_for_unmatched():
    assert classify_feature("main.dart") is None


def test_classify_feature_returns_none_for_bare_features_dir():
    assert classify_feature("features/readme.dart") is None
