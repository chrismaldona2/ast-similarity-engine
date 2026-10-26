import pytest
import find_similar as cli
import io
from pathlib import Path

SRC = (
    "def add_all(items):\n    t = 0\n    for x in items:\n        t = t + x\n    return t\n\n"
    "def sum_values(vals):\n    a = 0\n    for v in vals:\n        a = a + v\n    return a\n\n"
    "def greet(name):\n    return 'hi ' + name\n"
)


def _setup(tmp_path):
    (tmp_path / "mod.py").write_text(SRC, encoding="utf-8")
    return str(tmp_path)


def test_cli_finds_clone(tmp_path, capsys):
    root = _setup(tmp_path)
    code = cli.main(["--dir", root, "--function", "mod.py:add_all", "--top-k", "2", "--only-candidates"])
    out = capsys.readouterr().out
    assert code == 0
    assert "sum_values" in out and "[YES]" in out
    assert "greet" not in out


def test_cli_unknown_function_returns_error(tmp_path, capsys):
    code = cli.main(["--dir", _setup(tmp_path), "--function", "mod.py:nope"])
    assert code == 1
    assert "not found" in capsys.readouterr().err


def test_cli_query_file_works(tmp_path, capsys):
    root = _setup(tmp_path)
    query = tmp_path / "q.txt"
    query.write_text("def f(a):\n    s = 0\n    for i in a:\n        s = s + i\n    return s\n")
    code = cli.main(["--dir", root, "--query-file", str(query)])
    assert code == 0
    out = capsys.readouterr().out
    assert "add_all" in out
    assert "sum_values" in out


def test_cli_missing_directory(tmp_path, capsys):
    code = cli.main(["--dir", str(tmp_path / "missing"), "--function", "a.py:f"])
    assert code == 1
    assert "does not exist" in capsys.readouterr().err


def test_cli_query_from_stdin(tmp_path, capsys, monkeypatch):
    root = _setup(tmp_path)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO("def f(a):\n    s = 0\n    for i in a:\n        s = s + i\n    return s\n"),
    )
    assert cli.main(["--dir", root, "--query-file", "-"]) == 0
    assert "add_all" in capsys.readouterr().out


def test_cli_invalid_threshold(tmp_path, capsys):
    code = cli.main(["--dir", _setup(tmp_path), "--function", "mod.py:add_all", "--threshold", "1.5"])
    assert code == 1
    assert "between 0.0 and 1.0" in capsys.readouterr().err


def test_cli_only_candidates_empty_results(tmp_path, capsys):
    root = _setup(tmp_path)
    code = cli.main(["--dir", root, "--function", "mod.py:greet", "--only-candidates", "--threshold", "1.0"])
    assert code == 0
    out = capsys.readouterr().out
    assert "No matches found." in out
    

def test_cli_function_path_with_root_prefix(tmp_path, capsys):
    root = _setup(tmp_path)
    spec = f"{Path(root).as_posix()}/mod.py:add_all"
    
    code = cli.main(["--dir", root, "--function", spec])
    
    assert code == 0
    assert "sum_values" in capsys.readouterr().out


def test_cli_query_from_stdin_flags_candidate(tmp_path, capsys, monkeypatch):
    root = _setup(tmp_path)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO("def f(a):\n    s = 0\n    for i in a:\n        s = s + i\n    return s\n"),
    )
    assert cli.main(["--dir", root, "--query-file", "-"]) == 0
    out = capsys.readouterr().out
    assert "add_all" in out
    assert "[YES]" in out