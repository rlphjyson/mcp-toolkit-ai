import re
from dataclasses import dataclass


@dataclass
class MigrationRule:
    migration_id: str
    description: str
    pattern: re.Pattern[str]
    replacement: str | None
    category: str


# category="mechanical" means `replacement` is a genuine 1:1 find/replace: applying it is
# correct without understanding surrounding code, so transformer.py is allowed to auto-apply it.
# category="manual_required" means `replacement` is always None: the migration involves a
# semantic or structural change (a different callback signature, a different state-management
# model, a different navigation API) that a regex cannot safely perform -- these rules exist for
# detection and guidance only, never for automated rewriting.
MIGRATIONS: dict[str, list[MigrationRule]] = {
    "deprecated_widgets": [
        MigrationRule(
            migration_id="deprecated_widgets",
            description="RaisedButton is deprecated -- replace with ElevatedButton.",
            pattern=re.compile(r"\bRaisedButton\b"),
            replacement="ElevatedButton",
            category="mechanical",
        ),
        MigrationRule(
            migration_id="deprecated_widgets",
            description="FlatButton is deprecated -- replace with TextButton.",
            pattern=re.compile(r"\bFlatButton\b"),
            replacement="TextButton",
            category="mechanical",
        ),
        MigrationRule(
            migration_id="deprecated_widgets",
            description="OutlineButton is deprecated -- replace with OutlinedButton.",
            pattern=re.compile(r"\bOutlineButton\b"),
            replacement="OutlinedButton",
            category="mechanical",
        ),
        MigrationRule(
            migration_id="deprecated_widgets",
            description=(
                "Scaffold.of(context).showSnackBar( is deprecated -- replace with "
                "ScaffoldMessenger.of(context).showSnackBar(."
            ),
            pattern=re.compile(re.escape("Scaffold.of(context).showSnackBar(")),
            replacement="ScaffoldMessenger.of(context).showSnackBar(",
            category="mechanical",
        ),
        MigrationRule(
            migration_id="deprecated_widgets",
            description=(
                "WillPopScope is deprecated -- PopScope replaces it, but the callback signature "
                "changed (onWillPop returning a bool becomes canPop plus onPopInvoked). This is "
                "not a mechanical rename and requires manual review."
            ),
            pattern=re.compile(r"\bWillPopScope\b"),
            replacement=None,
            category="manual_required",
        ),
    ],
    "navigator_to_gorouter": [
        MigrationRule(
            migration_id="navigator_to_gorouter",
            description="Navigator.push call -- migrate to context.push() with a GoRouter route.",
            pattern=re.compile(re.escape("Navigator.push(")),
            replacement=None,
            category="manual_required",
        ),
        MigrationRule(
            migration_id="navigator_to_gorouter",
            description=(
                "Navigator.pushNamed call -- migrate to context.go()/context.push() with a "
                "GoRouter route."
            ),
            pattern=re.compile(re.escape("Navigator.pushNamed(")),
            replacement=None,
            category="manual_required",
        ),
        MigrationRule(
            migration_id="navigator_to_gorouter",
            description="Navigator.pop call -- migrate to context.pop() with GoRouter.",
            pattern=re.compile(re.escape("Navigator.pop(")),
            replacement=None,
            category="manual_required",
        ),
        MigrationRule(
            migration_id="navigator_to_gorouter",
            description=(
                "Navigator.pushReplacement call -- migrate to context.pushReplacement() with a "
                "GoRouter route."
            ),
            pattern=re.compile(re.escape("Navigator.pushReplacement(")),
            replacement=None,
            category="manual_required",
        ),
    ],
    "bloc_to_riverpod": [
        MigrationRule(
            migration_id="bloc_to_riverpod",
            description=(
                "Bloc subclass -- migrate the state class to a Riverpod Notifier/AsyncNotifier."
            ),
            pattern=re.compile(r"extends Bloc<"),
            replacement=None,
            category="manual_required",
        ),
        MigrationRule(
            migration_id="bloc_to_riverpod",
            description="Cubit subclass -- migrate the state class to a Riverpod Notifier.",
            pattern=re.compile(r"extends Cubit<"),
            replacement=None,
            category="manual_required",
        ),
        MigrationRule(
            migration_id="bloc_to_riverpod",
            description=(
                "BlocProvider usage -- migrate to Riverpod's ProviderScope and a generated "
                "provider, read via ref."
            ),
            pattern=re.compile(re.escape("BlocProvider(")),
            replacement=None,
            category="manual_required",
        ),
        MigrationRule(
            migration_id="bloc_to_riverpod",
            description=(
                "BlocBuilder usage -- migrate the widget to a ConsumerWidget and read state via "
                "ref.watch."
            ),
            pattern=re.compile(r"BlocBuilder<"),
            replacement=None,
            category="manual_required",
        ),
        MigrationRule(
            migration_id="bloc_to_riverpod",
            description=(
                "context.read<...Bloc>() call -- migrate to ref.read(...) against a Riverpod "
                "provider."
            ),
            pattern=re.compile(r"context\.read<.*Bloc>\(\)"),
            replacement=None,
            category="manual_required",
        ),
    ],
}


def require_known_migration(migration: str) -> None:
    if migration not in MIGRATIONS:
        valid = ", ".join(sorted(MIGRATIONS))
        raise ValueError(f"Unknown migration '{migration}'. Valid options: {valid}")
