import ast
import re

from src.models import FunctionNode
from src.normalizer import normalize_function

# Default to False for the reasons proven by calibrate.py 
# (better separation margin for reordered independent lines).
DEFAULT_INDEX_VARS = False

# Context nodes carry no structure and only add trivial, high-frequency n-grams.
_OMITTED_NODES = (ast.Load, ast.Store, ast.Del)

_VAR_INDEX = re.compile(r"(?<=:)VAR\d+$")


def _node_value(node: ast.AST) -> str | None:
    """Return the identifying value of a node, or None if its type is enough."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.arg):
        return node.arg
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant):
        return str(node.value)  # 'LIT', 'None', 'True', 'False' or 'Ellipsis'
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.keyword):
        return node.arg  # None for **kwargs
    if isinstance(node, ast.alias):
        return node.name
    if isinstance(node, ast.ImportFrom):
        return node.module  # None for relative imports like 'from . import x'
    if isinstance(node, ast.ExceptHandler):
        return node.name
    return None


def _token(node: ast.AST) -> str:
    """Build the single token for a node: 'Type' or 'Type:value'."""
    kind = type(node).__name__
    value = _node_value(node)
    return kind if value is None else f"{kind}:{value}"


def serialize_tree(node: ast.AST) -> list[str]:
    """Serialize an AST into a pre-order token sequence (one token per node)."""
    tokens: list[str] = []

    def visit(current: ast.AST) -> None:
        if isinstance(current, _OMITTED_NODES):
            return
        tokens.append(_token(current))
        for child in ast.iter_child_nodes(current):
            visit(child)

    visit(node)
    return tokens


def function_tokens(func: FunctionNode, index_vars: bool = DEFAULT_INDEX_VARS) -> list[str]:
    """Normalize a function and serialize it in pre-order.

    With index_vars=False, VAR1, VAR2, ... collapse into a single VAR token,
    making the sequence insensitive to variable numbering order.
    """
    tokens = serialize_tree(normalize_function(func))
    if not index_vars:
        tokens = [_VAR_INDEX.sub("VAR", token) for token in tokens]
    return tokens