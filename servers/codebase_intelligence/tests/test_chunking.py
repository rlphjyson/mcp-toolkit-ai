import pytest

from codebase_intelligence.chunking import chunk_repository, chunk_text, discover_files


def test_chunk_text_returns_empty_list_for_blank_input():
    assert chunk_text("   ") == []


def test_chunk_text_produces_overlapping_windows():
    text = "a" * 1000
    chunks = chunk_text(text, chunk_size=400, overlap=100)
    assert len(chunks) == 3
    assert chunks[0][-100:] == chunks[1][:100]


def test_chunk_text_rejects_overlap_ge_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=100, overlap=100)


def test_discover_files_skips_ignored_directories_and_extensions(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("noise")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")

    files = discover_files(tmp_path)

    assert files == [tmp_path / "src" / "main.py"]


def test_discover_files_skips_oversized_files(tmp_path):
    big_file = tmp_path / "generated.py"
    big_file.write_text("x = 1\n" * 200_000)  # well over MAX_FILE_SIZE_BYTES

    files = discover_files(tmp_path)

    assert files == []


def test_chunk_repository_tags_chunks_with_relative_posix_paths(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("def f():\n    return 1\n")

    chunks = chunk_repository(tmp_path)

    assert len(chunks) == 1
    assert chunks[0].relative_path == "pkg/mod.py"
    assert chunks[0].chunk_index == 0
