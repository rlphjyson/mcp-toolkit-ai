import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("CODEBASE_INTELLIGENCE_DATA_DIR", "./data")).resolve()
CHROMA_DIR = DATA_DIR / "chroma"
REGISTRY_PATH = DATA_DIR / "repos.json"
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Directories and extensions to skip when walking a repo to index -- avoids indexing build
# output, dependency trees, and version-control internals, which would otherwise dominate
# search results with noise.
SKIP_DIR_NAMES = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".chroma",
}
INDEXABLE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".rb", ".php",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".swift", ".md", ".mdx", ".sql", ".sh", ".yaml", ".yml",
    ".json", ".toml",
}
MAX_FILE_SIZE_BYTES = 512_000  # skip generated/vendored files that are unusually large
