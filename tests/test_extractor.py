import ast
import pytest

from src.extractor import (
    extract_functions,
    extract_functions_from_source,
    find_python_files,
)


def test_extract_top_level_nested_and_methods():
    source = """
def top_level(x):
    def inner(y):
        return y + 1
    return inner(x)


class Cart:
    def add(self, item):
        self.items.append(item)

    async def fetch(self):
        return 1
"""
    funcs = extract_functions_from_source(source, "sample_a.py")
    summary = [(f.name, f.qualified_name, f.lineno, f.is_async) for f in funcs]

    assert summary == [
        ("top_level", "top_level", 2, False),
        ("inner", "top_level.inner", 3, False),
        ("add", "Cart.add", 9, False),
        ("fetch", "Cart.fetch", 12, True),
    ]
    assert all(isinstance(f.node, (ast.FunctionDef, ast.AsyncFunctionDef)) for f in funcs)


def test_extract_functions_from_directory_and_skip_broken_files(tmp_path):
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "valid.py").write_text("def ok(a):\n    return a\n", encoding="utf-8")
    (sub / "broken.py").write_text("def broken(:\n    pass\n", encoding="utf-8")

    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "ignored.py").write_text("def ignored():\n    pass\n", encoding="utf-8")

    funcs = extract_functions(tmp_path)
    assert len(funcs) == 1
    assert funcs[0].name == "ok"
    assert funcs[0].qualified_name == "ok"
    assert funcs[0].file_path == "pkg/valid.py"
    assert funcs[0].identifier == "pkg/valid.py:ok"


def test_find_python_files_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_python_files(tmp_path / "missing")

    file_path = tmp_path / "single.py"
    file_path.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        find_python_files(file_path)