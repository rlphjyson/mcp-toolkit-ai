import pytest

from knowledge_base.notes import (
    create_note,
    discover_notes,
    extract_wikilinks,
    get_backlinks,
    get_note,
    resolve_vault_path,
    search_notes,
    slugify,
)


@pytest.fixture(name="vault")
def vault_fixture(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "apples.md").write_text("# Apples\n\nApples are a fruit. See [[Bananas]] too.\n")
    (vault / "bananas.md").write_text("# Bananas\n\nBananas are yellow.\n")
    (vault / "untitled.md").write_text("Just some text, no heading.\n")
    return vault


def test_discover_notes_finds_all_markdown_files(vault):
    notes = discover_notes(vault)
    assert {n.path for n in notes} == {"apples.md", "bananas.md", "untitled.md"}


def test_discover_notes_derives_title_from_heading(vault):
    notes = {n.path: n for n in discover_notes(vault)}
    assert notes["apples.md"].title == "Apples"


def test_discover_notes_falls_back_to_filename_stem(vault):
    notes = {n.path: n for n in discover_notes(vault)}
    assert notes["untitled.md"].title == "untitled"


def test_discover_notes_on_missing_vault_returns_empty(tmp_path):
    assert discover_notes(tmp_path / "does-not-exist") == []


def test_get_note_returns_content(vault):
    note = get_note(vault, "apples.md")
    assert "Apples are a fruit" in note.content


def test_get_note_raises_for_missing_note(vault):
    with pytest.raises(ValueError, match="No such note"):
        get_note(vault, "missing.md")


def test_resolve_vault_path_rejects_traversal(vault):
    with pytest.raises(ValueError, match="escapes"):
        resolve_vault_path(vault, "../secrets.txt")


def test_search_notes_matches_title(vault):
    # "apples.md" also matches: its body links to [[Bananas]], and search is substring-based
    # over content as well as title.
    results = search_notes(vault, "banana")
    assert {n.path for n in results} == {"apples.md", "bananas.md"}


def test_search_notes_matches_content(vault):
    results = search_notes(vault, "yellow")
    assert [n.path for n in results] == ["bananas.md"]


def test_search_notes_is_case_insensitive(vault):
    results = search_notes(vault, "APPLES")
    assert "apples.md" in [n.path for n in results]


def test_slugify_lowercases_and_hyphenates():
    assert slugify("My New Note!") == "my-new-note"


def test_slugify_falls_back_when_empty():
    assert slugify("!!!") == "note"


def test_create_note_writes_a_file(vault):
    note = create_note(vault, "My New Note", "Some content.")
    assert note.path == "my-new-note.md"
    assert (vault / "my-new-note.md").read_text().startswith("# My New Note")


def test_create_note_deduplicates_on_slug_collision(vault):
    # "apples.md" already exists from the fixture.
    first = create_note(vault, "Apples")
    second = create_note(vault, "Apples")
    assert first.path == "apples-2.md"
    assert second.path == "apples-3.md"


def test_extract_wikilinks_finds_plain_links():
    assert extract_wikilinks("See [[Bananas]] and [[Cherries]].") == ["Bananas", "Cherries"]


def test_extract_wikilinks_strips_display_text():
    assert extract_wikilinks("See [[Bananas|the yellow fruit]].") == ["Bananas"]


def test_get_backlinks_finds_linking_notes(vault):
    backlinks = get_backlinks(vault, "bananas.md")
    assert [n.path for n in backlinks] == ["apples.md"]


def test_get_backlinks_excludes_the_note_itself(vault):
    (vault / "bananas.md").write_text("# Bananas\n\nSee [[Bananas]] (self-link, should not count).\n")
    backlinks = get_backlinks(vault, "bananas.md")
    assert "bananas.md" not in [n.path for n in backlinks]


def test_get_backlinks_raises_for_unknown_note(vault):
    with pytest.raises(ValueError, match="No such note"):
        get_backlinks(vault, "missing.md")
