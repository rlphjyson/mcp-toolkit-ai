from flutter_architecture_guardian.feature_first_rules import check_feature_first
from flutter_architecture_guardian.layer_classifier import classify_feature

MARKERS = ["public", "api"]


def test_cross_feature_import_of_an_internal_file_is_a_violation():
    graph = {
        "features/checkout/cart_screen.dart": ["features/catalog/internal/pricing_engine.dart"],
        "features/catalog/internal/pricing_engine.dart": [],
    }
    violations = check_feature_first(graph, classify_feature, MARKERS)
    assert len(violations) == 1
    assert violations[0].rule == "cross_feature_import"
    assert violations[0].file == "features/checkout/cart_screen.dart"


def test_import_of_the_feature_barrel_file_is_allowed():
    graph = {
        "features/checkout/cart_screen.dart": ["features/catalog/catalog.dart"],
        "features/catalog/catalog.dart": [],
    }
    assert check_feature_first(graph, classify_feature, MARKERS) == []


def test_import_of_a_public_marker_directory_is_allowed():
    graph = {
        "features/checkout/cart_screen.dart": ["features/catalog/public/product_card.dart"],
        "features/catalog/public/product_card.dart": [],
    }
    assert check_feature_first(graph, classify_feature, MARKERS) == []


def test_import_within_the_same_feature_is_allowed():
    graph = {
        "features/checkout/cart_screen.dart": ["features/checkout/internal/cart_state.dart"],
        "features/checkout/internal/cart_state.dart": [],
    }
    assert check_feature_first(graph, classify_feature, MARKERS) == []


def test_import_of_core_is_always_allowed():
    graph = {
        "features/checkout/cart_screen.dart": ["core/widgets/button.dart"],
        "core/widgets/button.dart": [],
    }
    assert check_feature_first(graph, classify_feature, MARKERS) == []


def test_core_importing_a_feature_is_ignored():
    graph = {
        "core/widgets/button.dart": ["features/checkout/internal/cart_state.dart"],
        "features/checkout/internal/cart_state.dart": [],
    }
    assert check_feature_first(graph, classify_feature, MARKERS) == []


def test_unclassified_files_are_ignored():
    graph = {"main.dart": ["features/checkout/internal/cart_state.dart"]}
    assert check_feature_first(graph, classify_feature, MARKERS) == []
