import re
from dataclasses import dataclass
from pathlib import Path

TITLE_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
SLUG_INVALID_CHARS_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class Note:
    path: str  # relative to the vault, posix-style
    title: str
    content: str


def _title_from_content(content: str, fallback: str) -> str:
    match = TITLE_HEADING_RE.search(content)
    return match.group(1) if match else fallback


def resolve_vault_path(vault_dir: Path, relative_path: str) -> Path:
    vault_dir = vault_dir.resolve()
    target = (vault_dir / relative_path).resolve()
    if not target.is_relative_to(vault_dir):
        raise ValueError(f"Path escapes the vault directory: {relative_path}")
    return target


def discover_notes(vault_dir: Path) -> list[Note]:
    if not vault_dir.is_dir():
        return []
    notes = []
    for file_path in sorted(vault_dir.rglob("*.md")):
        relative = file_path.relative_to(vault_dir).as_posix()
        content = file_path.read_text(encoding="utf-8")
        notes.append(Note(path=relative, title=_title_from_content(content, file_path.stem), content=content))
    return notes


def get_note(vault_dir: Path, relative_path: str) -> Note:
    target = resolve_vault_path(vault_dir, relative_path)
    if not target.is_file():
        raise ValueError(f"No such note: {relative_path}")
    content = target.read_text(encoding="utf-8")
    return Note(path=relative_path, title=_title_from_content(content, target.stem), content=content)


def search_notes(vault_dir: Path, query: str) -> list[Note]:
    needle = query.lower()
    return [
        note
        for note in discover_notes(vault_dir)
        if needle in note.title.lower() or needle in note.content.lower()
    ]


def slugify(title: str) -> str:
    slug = SLUG_INVALID_CHARS_RE.sub("-", title.lower()).strip("-")
    return slug or "note"


def create_note(vault_dir: Path, title: str, content: str = "") -> Note:
    vault_dir.mkdir(parents=True, exist_ok=True)
    base_slug = slugify(title)
    slug = base_slug
    suffix = 2
    while (vault_dir / f"{slug}.md").exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    full_content = f"# {title}\n\n{content}\n"
    relative_path = f"{slug}.md"
    (vault_dir / relative_path).write_text(full_content, encoding="utf-8")
    return Note(path=relative_path, title=title, content=full_content)


def extract_wikilinks(content: str) -> list[str]:
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(content)]


def get_backlinks(vault_dir: Path, relative_path: str) -> list[Note]:
    target = get_note(vault_dir, relative_path)
    target_names = {target.title.lower(), Path(target.path).stem.lower()}

    backlinks = []
    for note in discover_notes(vault_dir):
        if note.path == target.path:
            continue
        links = {link.lower() for link in extract_wikilinks(note.content)}
        if links & target_names:
            backlinks.append(note)
    return backlinks
