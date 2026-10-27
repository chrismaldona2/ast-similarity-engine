import ast

from src.serializer import function_tokens, serialize_tree


def _func(source: str) -> ast.FunctionDef:
    return ast.parse(source).body[0]


def _tokens(source: str, **kwargs) -> list[str]:
    return function_tokens(_func(source), **kwargs)


def test_exact_preorder_sequence():
    assert _tokens("def sumar(a, b):\n    total = a + b\n    return total\n", index_vars=True) == [
        "FunctionDef:FUNC",
        "arguments",
        "arg:VAR1",
        "arg:VAR2",
        "Assign",
        "Name:VAR3",
        "BinOp",
        "Name:VAR1",
        "Add",
        "Name:VAR2",
        "Return",
        "Name:VAR3",
    ]


def test_renamed_clones_have_identical_tokens():
    a = "def sumar(a, b):\n    total = a + b\n    return total\n"
    b = "def calcular(x, y):\n    result = x + y\n    return result\n"
    assert _tokens(a) == _tokens(b)


def test_context_nodes_are_omitted():
    tokens = _tokens("def f(a):\n    b = a\n    del b\n")
    assert not {"Load", "Store", "Del"} & set(tokens)


def test_parent_comes_before_children():
    tokens = _tokens("def f(a):\n    return a + 1\n")
    assert tokens.index("Return") < tokens.index("BinOp") < tokens.index("Add")


def test_attribute_name_and_literals_are_in_tokens():
    tokens = _tokens("def f(items, v):\n    items.append(v)\n    return None\n", index_vars=True)
    assert tokens[tokens.index("Attribute:append") - 2 :][:5] == [
        "Expr",
        "Call",
        "Attribute:append",
        "Name:VAR1",
        "Name:VAR2",
    ]
    assert "Constant:None" in tokens
    assert "Constant:LIT" in _tokens("def f():\n    return 5\n", index_vars=True)


def test_index_vars_false_collapses_numbering():
    tokens = _tokens("def f(a, b):\n    return a + b\n", index_vars=False)
    assert "Name:VAR" in tokens and "arg:VAR" in tokens
    assert not any(t.endswith(("VAR1", "VAR2")) for t in tokens)


def test_reordered_lines_differ_only_in_numbering():
    a = "def f(a):\n    x = a + 1\n    y = a * 2\n    return x\n"
    b = "def f(a):\n    y = a * 2\n    x = a + 1\n    return x\n"
    # Same multiset of nodes after dropping the numbering
    assert sorted(_tokens(a, index_vars=False)) == sorted(_tokens(b, index_vars=False))
    # but different sequences, as expected for reordered statements.
    assert _tokens(a, index_vars=True) != _tokens(b, index_vars=True) 


def test_serialize_tree_is_deterministic():
    src = "def f(a):\n    return [n for n in a]\n"
    assert function_tokens(_func(src)) == function_tokens(_func(src))


def test_import_from_and_kwargs_tokens():
    tokens = _tokens("def f(**kw):\n    from os import path\n    return g(a=1, **kw)\n")
    assert "ImportFrom:os" in tokens
    assert "alias:path" in tokens
    assert "keyword:a" in tokens
    assert "keyword" in tokens  # **kw has arg=None, so it emits plain 'keyword'