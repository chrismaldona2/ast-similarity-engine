import ast
import copy

from src.models import FunctionNode

FUNCTION_TOKEN = "FUNC"
LITERAL_TOKEN = "LIT"

# Constants with structural/control meaning (`x is None`, `return True`) are kept.
_KEPT_CONSTANTS = (None, True, False, Ellipsis)


class _BoundNameCollector(ast.NodeVisitor):
    """Collects identifiers bound in a function scope without crossing into nested scopes."""

    def __init__(self, root: FunctionNode):
        self.root = root
        self.bound: set[str] = set()
        self.declared_free: set[str] = set()

    def visit(self, node: ast.AST) -> None:
        # Stop descending into the body of nested functions or classes
        if node is not self.root and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            self.bound.add(node.name)
            return

        if isinstance(node, ast.arg):
            self.bound.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            self.bound.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            self.bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            self.declared_free.update(node.names)

        self.generic_visit(node)


def collect_bound_names(func: FunctionNode) -> set[str]:
    """Return the identifiers bound inside a function's own scope (its local symbol table).

    Bound names are parameters, assignment/for/with/comprehension targets,
    walrus targets, except-as names, and nested def/class names.
    Names declared 'global' or 'nonlocal' in this scope are excluded.
    """
    collector = _BoundNameCollector(func)
    collector.visit(func)
    return collector.bound - collector.declared_free


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    """Remove a leading docstring; never leave the body empty."""
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return body or [ast.Pass()]


class _Normalizer(ast.NodeTransformer):
    """Rewrites one function AST into its canonical form, using its own symbol table."""

    def __init__(self, root: FunctionNode, bound: set[str]):
        self._root = root
        self._root_name = root.name
        self._bound = bound
        self._mapping: dict[str, str] = {}

    def _rename(self, name: str) -> str:
        """Map a local name to VARn, numbered by first appearance in traversal."""
        if name not in self._bound:
            return name
        if name not in self._mapping:
            self._mapping[name] = f"VAR{len(self._mapping) + 1}"
        return self._mapping[name]

    # Definitions 
    def _visit_function(self, node: FunctionNode) -> FunctionNode:
        if node is not self._root:
            # Nested function: its name belongs to this scope, its body to its own.
            nested_name = self._rename(node.name)
            nested = normalize_function(node)
            nested.name = nested_name
            return nested

        node.name = FUNCTION_TOKEN
        node.returns = None
        if hasattr(node, "type_params"):
            node.type_params = []
        node.body = _strip_docstring(node.body)
        self.generic_visit(node)
        return node

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        node.name = self._rename(node.name)
        node.bases = [self.visit(b) for b in node.bases]
        node.keywords = [self.visit(k) for k in node.keywords]
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.body = _strip_docstring(node.body)
        new_body: list[ast.stmt] = []
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                new_body.append(normalize_function(stmt))
            else:
                new_body.append(stmt)
        node.body = new_body
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg = self._rename(node.arg)
        node.annotation = None
        return node

    # Names
    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in self._bound:
            node.id = self._rename(node.id)
        elif node.id == self._root_name:
            node.id = FUNCTION_TOKEN  # Recursive call to itself
        return node

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler:
        if node.name:
            node.name = self._rename(node.name)
        self.generic_visit(node)
        return node

    # Annotations and literals
    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AST:
        if node.value is None:  # Bare declaration `x: int`
            return ast.copy_location(ast.Pass(), node)
        assign = ast.Assign(
            targets=[node.target], value=node.value, type_comment=None
        )
        return self.visit(ast.copy_location(assign, node))

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        if any(node.value is kept for kept in _KEPT_CONSTANTS):
            return node
        return ast.copy_location(ast.Constant(value=LITERAL_TOKEN), node)


def normalize_function(func: FunctionNode) -> FunctionNode:
    """Return a normalized deep copy of a function AST (the input is not modified)."""
    tree = copy.deepcopy(func)
    bound = collect_bound_names(tree)
    return _Normalizer(tree, bound).visit(tree)