import ast

SOURCE = '''
def add_scaled(a, b, factor=2):
    """Add two numbers and scale the result."""
    total = a + b
    if total > 10:
        print("big")
    return total * factor
'''

tree = ast.parse(SOURCE)

# Full tree as Python builds it
print("=== ast.dump ===")
print(ast.dump(tree, indent=2))

# Regenerated source 
print("\n=== ast.unparse ===")
print(ast.unparse(tree))

# Traversal order
print("\n=== ast.walk (BFS) ===")
print([type(n).__name__ for n in ast.walk(tree)])

def preorder(node):
    yield node
    for child in ast.iter_child_nodes(node):
        yield from preorder(child)

print("\n=== pre-order (DFS) ===")
print([type(n).__name__ for n in preorder(tree)])

# Nodes location
print("\n=== Interesting nodes ===")
for n in ast.walk(tree):
    if isinstance(n, ast.arg):
        print("arg      ->", n.arg)
    elif isinstance(n, ast.Name):
        print("Name     ->", n.id, type(n.ctx).__name__)
    elif isinstance(n, ast.Constant):
        print("Constant ->", repr(n.value))
    elif isinstance(n, ast.Call):
        print("Call     -> func is", type(n.func).__name__)