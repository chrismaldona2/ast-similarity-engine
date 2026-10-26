import ast
import logging
import os
from pathlib import Path

from src.models import FunctionInfo

logger = logging.getLogger(__name__)

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".pytest_cache",
    "node_modules",
}


def find_python_files(root: str | Path) -> list[Path]:
    """Recursively list .py files under root, pruning ignored directories."""
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(f"Directory not found: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {root_path}")

    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                files.append(Path(dirpath) / filename)
    return files


def parse_file(path: str | Path) -> ast.Module | None:
    """Parse a Python file; return None (and log a warning) if it cannot be parsed."""
    file_path = Path(path)
    try:
        source = file_path.read_text(encoding="utf-8-sig")
        return ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, ValueError, OSError) as exc:
        logger.warning("Skipping %s: %s", file_path, exc)
        return None


class _FunctionCollector(ast.NodeVisitor):
    """Collects every function in pre-order, tracking class and function scope."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.scope: list[str] = []
        self.functions: list[FunctionInfo] = []

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.functions.append(
            FunctionInfo(
                name=node.name,
                qualified_name=".".join([*self.scope, node.name]),
                file_path=self.file_path,
                lineno=node.lineno,
                node=node,
                is_async=isinstance(node, ast.AsyncFunctionDef),
            )
        )
        self.scope.append(node.name)
        self.generic_visit(node)  # Continue traversal to find nested functions
        self.scope.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()


def extract_functions_from_tree(
    tree: ast.AST, file_path: str = "<string>"
) -> list[FunctionInfo]:
    """Extract all FunctionInfo objects from an AST."""
    collector = _FunctionCollector(file_path)
    collector.visit(tree)
    return collector.functions


def extract_functions_from_source(
    source: str, file_path: str = "<string>"
) -> list[FunctionInfo]:
    """Parse Python source code from a string and extract all functions."""
    tree = ast.parse(source, filename=file_path)
    return extract_functions_from_tree(tree, file_path)


def extract_functions_from_file(
    file_path: str | Path, root_dir: str | Path | None = None
) -> list[FunctionInfo]:
    """Extract function definitions from a single Python file."""
    path_obj = Path(file_path)
    tree = parse_file(path_obj)
    if tree is None:
        return []

    if root_dir is not None:
        rel_path = path_obj.resolve().relative_to(Path(root_dir).resolve()).as_posix()
    else:
        rel_path = path_obj.as_posix()

    return extract_functions_from_tree(tree, rel_path)


def extract_functions(root: str | Path) -> list[FunctionInfo]:
    """Extract all functions from every parseable .py file under root."""
    root_path = Path(root)
    functions: list[FunctionInfo] = []
    for path in find_python_files(root_path):
        functions.extend(extract_functions_from_file(path, root_path))
    return functions