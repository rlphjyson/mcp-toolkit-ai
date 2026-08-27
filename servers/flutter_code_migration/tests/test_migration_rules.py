import pytest

from flutter_code_migration.migration_rules import MIGRATIONS, require_known_migration


def _rule(migration: str, matched_text: str):
    for rule in MIGRATIONS[migration]:
        if rule.pattern.search(matched_text):
            return rule
    return None


@pytest.mark.parametrize(
    "snippet,replacement",
    [
        ("RaisedButton(onPressed: () {}, child: Text('x'))", "ElevatedButton"),
        ("FlatButton(onPressed: () {})", "TextButton"),
        ("OutlineButton(onPressed: () {})", "OutlinedButton"),
        ("Scaffold.of(context).showSnackBar(SnackBar())", "ScaffoldMessenger.of(context).showSnackBar("),
    ],
)
def test_deprecated_widgets_mechanical_rules_match_and_replace(snippet, replacement):
    rule = _rule("deprecated_widgets", snippet)
    assert rule is not None
    assert rule.category == "mechanical"
    assert rule.replacement is not None
    transformed = rule.pattern.sub(rule.replacement, snippet)
    assert replacement in transformed


def test_deprecated_widgets_does_not_match_button_theme():
    for rule in MIGRATIONS["deprecated_widgets"]:
        assert not rule.pattern.search("ButtonTheme.of(context)")


def test_will_pop_scope_is_manual_required_with_no_replacement():
    rule = _rule("deprecated_widgets", "class Foo extends WillPopScope {}")
    assert rule is not None
    assert rule.category == "manual_required"
    assert rule.replacement is None
    assert "PopScope" in rule.description


@pytest.mark.parametrize(
    "snippet",
    [
        "Navigator.push(context, MaterialPageRoute(builder: (c) => Foo()))",
        "Navigator.pushNamed(context, '/foo')",
        "Navigator.pop(context)",
        "Navigator.pushReplacement(context, route)",
    ],
)
def test_navigator_to_gorouter_rules_are_all_manual_required(snippet):
    rule = _rule("navigator_to_gorouter", snippet)
    assert rule is not None
    assert rule.category == "manual_required"
    assert rule.replacement is None


def test_navigator_to_gorouter_has_no_mechanical_rules():
    assert all(rule.replacement is None for rule in MIGRATIONS["navigator_to_gorouter"])


@pytest.mark.parametrize(
    "snippet",
    [
        "class CounterBloc extends Bloc<CounterEvent, int> {}",
        "class CounterCubit extends Cubit<int> {}",
        "BlocProvider(create: (_) => CounterBloc())",
        "BlocBuilder<CounterBloc, int>(builder: (context, state) => Text('$state'))",
        "context.read<CounterBloc>().add(Increment())",
    ],
)
def test_bloc_to_riverpod_rules_are_all_manual_required(snippet):
    rule = _rule("bloc_to_riverpod", snippet)
    assert rule is not None
    assert rule.category == "manual_required"
    assert rule.replacement is None


def test_bloc_to_riverpod_has_no_mechanical_rules():
    assert all(rule.replacement is None for rule in MIGRATIONS["bloc_to_riverpod"])


def test_require_known_migration_accepts_known_keys():
    for migration in MIGRATIONS:
        require_known_migration(migration)


def test_require_known_migration_rejects_unknown_key():
    with pytest.raises(ValueError, match="Unknown migration"):
        require_known_migration("not_a_real_migration")
