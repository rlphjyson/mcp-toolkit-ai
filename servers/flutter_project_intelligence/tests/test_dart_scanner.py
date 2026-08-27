from flutter_project_intelligence.dart_scanner import discover_dart_files, scan_file


def test_scan_file_classifies_stateless_widget():
    text = (
        "import 'package:flutter/material.dart';\n"
        "\n"
        "class HomeScreen extends StatelessWidget {\n"
        "  @override\n"
        "  Widget build(BuildContext context) => Container();\n"
        "}\n"
    )

    scan = scan_file(text, "lib/home_screen.dart")

    assert scan.imports == ["package:flutter/material.dart"]
    assert len(scan.symbols) == 1
    symbol = scan.symbols[0]
    assert symbol.name == "HomeScreen"
    assert symbol.kind == "widget"
    assert symbol.base_class == "StatelessWidget"
    assert symbol.file == "lib/home_screen.dart"
    assert symbol.line == 3


def test_scan_file_classifies_bloc_and_cubit():
    text = (
        "class CounterEvent {}\n"
        "\n"
        "class CounterBloc extends Bloc<CounterEvent, int> {\n"
        "  CounterBloc() : super(0);\n"
        "}\n"
        "\n"
        "class CounterCubit extends Cubit<int> {\n"
        "  CounterCubit() : super(0);\n"
        "}\n"
    )

    scan = scan_file(text, "lib/counter.dart")
    by_name = {s.name: s for s in scan.symbols}

    assert by_name["CounterEvent"].kind == "other"
    assert by_name["CounterBloc"].kind == "state_management"
    assert by_name["CounterBloc"].state_kind == "bloc"
    assert by_name["CounterBloc"].line == 3
    assert by_name["CounterCubit"].kind == "state_management"
    assert by_name["CounterCubit"].state_kind == "cubit"
    assert by_name["CounterCubit"].line == 7


def test_scan_file_classifies_riverpod_notifier_and_providers():
    text = (
        "@riverpod\n"
        "class Counter extends _$Counter {\n"
        "  @override\n"
        "  int build() => 0;\n"
        "}\n"
        "\n"
        "@riverpod\n"
        "FooRepository fooRepository(FooRepositoryRef ref) {\n"
        "  return FooRepositoryImpl();\n"
        "}\n"
        "\n"
        "final counterProvider = StateProvider<int>((ref) => 0);\n"
    )

    scan = scan_file(text, "lib/providers.dart")
    by_name = {s.name: s for s in scan.symbols}

    assert by_name["Counter"].kind == "state_management"
    assert by_name["Counter"].state_kind == "riverpod_notifier"
    assert by_name["Counter"].line == 2

    assert by_name["fooRepository"].kind == "state_management"
    assert by_name["fooRepository"].state_kind == "riverpod_provider"
    assert by_name["fooRepository"].line == 8

    assert by_name["counterProvider"].kind == "state_management"
    assert by_name["counterProvider"].state_kind == "riverpod_provider"
    assert by_name["counterProvider"].line == 12


def test_scan_file_classifies_state_notifier_by_extends():
    text = "class CounterNotifier extends StateNotifier<int> {\n  CounterNotifier() : super(0);\n}\n"

    scan = scan_file(text, "lib/counter_notifier.dart")

    symbol = scan.symbols[0]
    assert symbol.kind == "state_management"
    assert symbol.state_kind == "riverpod_notifier"
    assert symbol.base_class == "StateNotifier"


def test_scan_file_classifies_repository_and_use_case():
    text = (
        "class UserRepository {\n"
        "  Future<void> save() async {}\n"
        "}\n"
        "\n"
        "class UserRepositoryImpl extends UserRepository {\n"
        "  @override\n"
        "  Future<void> save() async {}\n"
        "}\n"
        "\n"
        "class GetUserUseCase {\n"
        "  Future<void> call(String id) async {}\n"
        "}\n"
        "\n"
        "class FetchProfile {\n"
        "  Future<void> call() async {}\n"
        "}\n"
    )

    scan = scan_file(text, "lib/user.dart")
    by_name = {s.name: s for s in scan.symbols}

    assert by_name["UserRepository"].kind == "repository"
    assert by_name["UserRepositoryImpl"].kind == "repository"
    assert by_name["GetUserUseCase"].kind == "use_case"
    assert by_name["FetchProfile"].kind == "use_case"  # classified via the single call() heuristic


def test_scan_file_classifies_api_clients():
    text = (
        "class AuthApiClient {\n"
        "  final Dio dio = Dio();\n"
        "}\n"
        "\n"
        "class NetworkGateway {\n"
        "  final Dio client = Dio();\n"
        "}\n"
    )

    scan = scan_file(text, "lib/network.dart")
    by_name = {s.name: s for s in scan.symbols}

    assert by_name["AuthApiClient"].kind == "api_client"
    assert by_name["NetworkGateway"].kind == "api_client"  # classified via the Dio() heuristic


def test_scan_file_finds_go_router_routes():
    text = (
        "final router = GoRouter(\n"
        "  routes: [\n"
        "    GoRoute(\n"
        "      path: '/home',\n"
        "      builder: (context, state) => const HomeScreen(),\n"
        "    ),\n"
        "  ],\n"
        ");\n"
    )

    scan = scan_file(text, "lib/router.dart")

    assert len(scan.routes) == 1
    route = scan.routes[0]
    assert route.path == "/home"
    assert route.source == "go_router"
    assert route.line == 3


def test_scan_file_finds_named_routes_table():
    text = (
        "class Routes {\n"
        "  static Map<String, WidgetBuilder> routes = {\n"
        "    '/login': (context) => LoginScreen(),\n"
        "    '/home': (context) => HomeScreen(),\n"
        "  };\n"
        "}\n"
    )

    scan = scan_file(text, "lib/routes.dart")
    by_path = {r.path: r for r in scan.routes}

    assert by_path.keys() == {"/login", "/home"}
    assert by_path["/login"].source == "named_route"
    assert by_path["/login"].line == 3
    assert by_path["/home"].line == 4


def test_scan_file_collects_raw_imports():
    text = (
        "import 'package:my_app/repositories/user_repository.dart';\n"
        "import '../models/user.dart';\n"
        "import 'dart:async';\n"
        "\n"
        "class Foo {}\n"
    )

    scan = scan_file(text, "lib/features/foo.dart")

    assert scan.imports == [
        "package:my_app/repositories/user_repository.dart",
        "../models/user.dart",
        "dart:async",
    ]


def test_discover_dart_files_finds_all_dart_files_under_lib(tmp_path):
    lib_dir = tmp_path / "lib"
    (lib_dir / "widgets").mkdir(parents=True)
    (lib_dir / "main.dart").write_text("void main() {}\n")
    (lib_dir / "widgets" / "home.dart").write_text("class Home {}\n")
    (lib_dir / "widgets" / "home.g.dart").write_text("// generated\n")

    files = discover_dart_files(lib_dir)

    assert {p.name for p in files} == {"main.dart", "home.dart", "home.g.dart"}


def test_discover_dart_files_skips_oversized_files(tmp_path, monkeypatch):
    monkeypatch.setattr("flutter_project_intelligence.dart_scanner.MAX_DART_FILE_SIZE_BYTES", 10)
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "big.dart").write_text("class TooBig {}\n")

    files = discover_dart_files(lib_dir)

    assert files == []
