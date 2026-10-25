import ast
from dataclasses import dataclass

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class FunctionInfo:
    """A function definition extracted from a Python source file."""

    name: str
    qualified_name: str
    file_path: str
    lineno: int
    node: FunctionNode
    is_async: bool = False

    @property
    def identifier(self) -> str:
        """Canonical identifier in 'file_path:qualified_name' format."""
        return f"{self.file_path}:{self.qualified_name}"