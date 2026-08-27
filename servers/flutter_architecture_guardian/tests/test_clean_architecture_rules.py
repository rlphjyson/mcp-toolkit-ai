from flutter_architecture_guardian.clean_architecture_rules import check_clean_architecture
from flutter_architecture_guardian.layer_classifier import classify_clean_layer


def test_domain_importing_presentation_is_a_violation():
    graph = {
        "domain/use_case.dart": ["presentation/home_screen.dart"],
        "presentation/home_screen.dart": [],
    }
    violations = check_clean_architecture(graph, classify_clean_layer)
    assert len(violations) == 1
    assert violations[0].rule == "domain_imports_presentation"
    assert violations[0].file == "domain/use_case.dart"
    assert violations[0].imported_file == "presentation/home_screen.dart"


def test_domain_importing_data_is_a_violation():
    graph = {
        "domain/use_case.dart": ["data/repository_impl.dart"],
        "data/repository_impl.dart": [],
    }
    violations = check_clean_architecture(graph, classify_clean_layer)
    assert [v.rule for v in violations] == ["domain_imports_data"]


def test_presentation_importing_data_is_a_violation():
    graph = {
        "presentation/home_screen.dart": ["data/repository_impl.dart"],
        "data/repository_impl.dart": [],
    }
    violations = check_clean_architecture(graph, classify_clean_layer)
    assert [v.rule for v in violations] == ["presentation_imports_data"]


def test_presentation_importing_domain_is_allowed():
    graph = {
        "presentation/home_screen.dart": ["domain/entities/user.dart"],
        "domain/entities/user.dart": [],
    }
    assert check_clean_architecture(graph, classify_clean_layer) == []


def test_data_importing_domain_is_allowed():
    graph = {
        "data/repository_impl.dart": ["domain/entities/user.dart"],
        "domain/entities/user.dart": [],
    }
    assert check_clean_architecture(graph, classify_clean_layer) == []


def test_unclassified_files_are_ignored():
    graph = {"main.dart": ["presentation/home_screen.dart"], "presentation/home_screen.dart": []}
    assert check_clean_architecture(graph, classify_clean_layer) == []


def test_import_within_the_same_layer_is_allowed():
    graph = {
        "domain/use_case.dart": ["domain/entities/user.dart"],
        "domain/entities/user.dart": [],
    }
    assert check_clean_architecture(graph, classify_clean_layer) == []
