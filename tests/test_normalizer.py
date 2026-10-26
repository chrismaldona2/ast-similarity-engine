import ast

from src.normalizer import collect_bound_names, normalize_function


def _func(source: str) -> ast.FunctionDef:
    return ast.parse(source).body[0]


def _norm(source: str) -> str:
    return ast.unparse(normalize_function(_func(source)))


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


def test_renamed_clones_normalize_identically():
    a = "def sumar(a, b):\n    total = a + b\n    return total\n"
    b = "def calcular(x, y):\n    result = x + y\n    return result\n"
    assert _norm(a) == _norm(b)
    assert _norm(a) == "def FUNC(VAR1, VAR2):\n    VAR3 = VAR1 + VAR2\n    return VAR3"


def test_docstring_annotations_and_literals_are_removed():
    src = (
        'def f(a: int, b: str = "x") -> bool:\n'
        '    """Doc."""\n'
        "    c: int = a * 2\n"
        "    return c\n"
    )
    assert _norm(src) == (
        "def FUNC(VAR1, VAR2='LIT'):\n    VAR3 = VAR1 * 'LIT'\n    return VAR3"
    )


def test_free_names_and_attributes_are_preserved():
    assert "print(" in _norm("def f(x):\n    print(x)\n")
    assert "foo(" in _norm("def f(x):\n    foo(x)\n")
    assert "VAR1.append(VAR2)" in _norm("def f(items, v):\n    items.append(v)\n")


def test_called_parameter_is_normalized():
    assert _norm("def f(cb, x):\n    return cb(x)\n").endswith("return VAR1(VAR2)")


def test_recursive_call_uses_func_token():
    assert "FUNC(VAR1 - 'LIT')" in _norm(
        "def fact(n):\n    return n * fact(n - 1)\n"
    )


def test_fstring_keeps_structure():
    out = _norm('def f(n):\n    return f"n={n}"\n')
    assert "VAR1" in out and "n=" not in out


def test_none_and_booleans_are_kept():
    out = _norm("def f(x):\n    if x is None:\n        return False\n    return True\n")
    assert "None" in out and "False" in out and "True" in out


def test_original_tree_is_not_modified():
    func = _func("def f(a):\n    return a + 1\n")
    normalize_function(func)
    assert ast.unparse(func) == "def f(a):\n    return a + 1"


def test_closure_variables_stay_free_in_nested_function():
    out = _norm(
        "def f(a):\n"
        "    k = a\n"
        "    def g(x):\n"
        "        return x + k\n"
        "    return g\n"
    )
    assert "VAR1 + k" in out
    
    
def test_nested_function_is_normalized_independently():
    out = _norm("def f(a):\n    def g(x):\n        return x * 2\n    return g(a)\n")
    assert "def VAR2(VAR1):" in out
    assert "return VAR2(VAR1)" in out


def test_comprehension_clones_normalize_identically():
    a = "def f(items):\n    return [n * n for n in items]\n"
    b = "def g(lista):\n    return [x * x for x in lista]\n"
    assert _norm(a) == _norm(b)


def test_lambda_parameters_are_normalized():
    out = _norm("def f(xs):\n    return sorted(xs, key=lambda v: v[0])\n")
    assert "sorted(" in out and "lambda VAR2:" in out


def test_local_import_alias_stays_free():
    out = _norm("def f(x):\n    import math as m\n    return m.sqrt(x)\n")
    assert "import math as m" in out
    assert "m.sqrt(VAR1)" in out


def test_nested_class_scope_is_isolated():
    out = _norm(
        "def f(a):\n"
        "    class Box:\n"
        "        a = 10\n"
        "        def get(self, x):\n"
        "            return x\n"
        "    return Box()\n"
    )
    assert "class VAR2:" in out
    assert "a = 10" in out  # class attribute 'a' is not renamed to outer VAR1
    assert "def FUNC(VAR1, VAR2):" in out