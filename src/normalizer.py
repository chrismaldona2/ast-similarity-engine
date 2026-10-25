import ast
from src.models import FunctionNode


class _BoundNameCollector(ast.NodeVisitor):
    """Collects identifiers bound in a function scope without crossing into nested scopes."""

    def __init__(self, root: FunctionNode):
        self.root = root
        self.bound: set[str] = set()
        self.declared_free: set[str] = set()

    def visit(self, node: ast.AST) -> None:
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
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            self.bound.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            self.bound.add(node.rest)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            self.declared_free.update(node.names)

        self.generic_visit(node)


def collect_bound_names(func: FunctionNode) -> set[str]:
    """Return the identifiers bound inside a function's own scope (its local symbol table).

    Bound names are parameters, assignment/for/with/comprehension targets,
    walrus targets, except-as names, match captures and nested def/class names.
    Names declared 'global' or 'nonlocal' in this scope are excluded.
    """
    collector = _BoundNameCollector(func)
    collector.visit(func)
    return collector.bound - collector.declared_free