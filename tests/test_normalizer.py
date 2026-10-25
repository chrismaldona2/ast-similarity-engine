import ast

from src.normalizer import collect_bound_names


def _func(source: str) -> ast.FunctionDef:
    return ast.parse(source).body[0]


def test_bound_names_basic():
    func = _func(
        "def f(a, b=1, *args, k, **kw):\n"
        "    total = a + b\n"
        "    for i in range(3):\n"
        "        print(i)\n"
        "    return total\n"
    )
    assert collect_bound_names(func) == {"a", "b", "args", "k", "kw", "total", "i"}


def test_free_names_are_not_bound():
    func = _func("def f(x):\n    return len(x) + helper(x)\n")
    bound = collect_bound_names(func)
    assert "len" not in bound and "helper" not in bound


def test_other_binding_forms():
    func = _func(
        "def f(items):\n"
        "    with open('f') as fh:\n"
        "        pass\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as err:\n"
        "        pass\n"
        "    squares = [n * n for n in items]\n"
        "    if (m := len(items)) > 1:\n"
        "        pass\n"
    )
    assert collect_bound_names(func) >= {"items", "fh", "err", "squares", "n", "m"}


def test_global_declaration_is_free():
    func = _func("def f():\n    global counter\n    counter = 1\n")
    assert "counter" not in collect_bound_names(func)
    
    
def test_nested_function_scope_isolation():
    func = _func(
        "def outer(value):\n"
        "    result = value + 1\n"
        "    def inner(number):\n"
        "        global result\n"
        "        temporary = number * 2\n"
        "        return temporary\n"
        "    return result\n"
    )
    assert collect_bound_names(func) == {"value", "result", "inner"}