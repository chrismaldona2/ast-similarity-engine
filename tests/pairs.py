import ast
import textwrap


def parse_fn(code: str) -> ast.FunctionDef:
    tree = ast.parse(textwrap.dedent(code).strip())
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


PAIRS: list[tuple[str, bool, str, str]] = [
    # Positive cases (clones)
    (
        "C1: Renamed vars & literals",
        True,
        """
        def calc_discount(price: float, rate: float = 0.15) -> float:
            \"\"\"Apply discount with floor.\"\"\"
            discounted = price * (1.0 - rate)
            if discounted < 10.0:
                return 10.0
            return discounted
        """,
        """
        def apply_rebate(amount, pct=0.20):
            res = amount * (100 - pct)
            if res < 50:
                return 50
            return res
        """,
    ),
    (
        "C2: Reordered independent lines",
        True,
        """
        def summary_stats(numbers):
            n = len(numbers)
            total = sum(numbers)
            mean = total / n
            high = max(numbers)
            low = min(numbers)
            spread = high - low
            return mean, spread
        """,
        """
        def compute_metrics(values):
            high = max(values)
            low = min(values)
            spread = high - low
            total = sum(values)
            n = len(values)
            mean = total / n
            return mean, spread
        """,
    ),
    (
        "C3: Clone + 1 extra guard line",
        True,
        """
        def filter_positives(items):
            result = []
            for x in items:
                if x > 0:
                    result.append(x * 2)
            return result
        """,
        """
        def collect_valid(data):
            if data is None:
                return []
            out = []
            for elem in data:
                if elem > 0:
                    out.append(elem * 10)
            return out
        """,
    ),
    (
        "C4: Clone with extra logging",
        True,
        """
        def find_index(seq, target):
            for idx, val in enumerate(seq):
                if val == target:
                    return idx
            return -1
        """,
        """
        def locate_item(items, key):
            for i, current in enumerate(items):
                if current == key:
                    print("Found")
                    return i
            return -1
        """,
    ),
    # Negative cases (non-clones)
    (
        "N1: Loop sum vs max search",
        False,
        """
        def sum_even(numbers):
            acc = 0
            for n in numbers:
                if n % 2 == 0:
                    acc = acc + n
            return acc
        """,
        """
        def find_max(numbers):
            best = None
            for n in numbers:
                if best is None or n > best:
                    best = n
            return best
        """,
    ),
    (
        "N2: Validation vs dict count",
        False,
        """
        def validate_user(age, name):
            if age < 18:
                raise ValueError("underage")
            if not name:
                return False
            return True
        """,
        """
        def count_frequencies(words):
            counts = {}
            for w in words:
                counts[w] = counts.get(w, 0) + 1
            return counts
        """,
    ),
    (
        "N3: Binary search vs bubble",
        False,
        """
        def binary_search(arr, x):
            low = 0
            high = len(arr) - 1
            while low <= high:
                mid = (low + high) // 2
                if arr[mid] < x:
                    low = mid + 1
                elif arr[mid] > x:
                    high = mid - 1
                else:
                    return mid
            return -1
        """,
        """
        def bubble_sort(arr):
            n = len(arr)
            for i in range(n):
                for j in range(0, n - i - 1):
                    if arr[j] > arr[j + 1]:
                        arr[j], arr[j + 1] = arr[j + 1], arr[j]
            return arr
        """,
    ),
    (
        "N4: Recursive fact vs fib loop",
        False,
        """
        def factorial(n):
            if n <= 1:
                return 1
            return n * factorial(n - 1)
        """,
        """
        def fib_iter(n):
            a = 0
            b = 1
            for _ in range(n):
                a, b = b, a + b
            return a
        """,
    ),
    (
        "N5: Loop list div vs dict strip",
        False,
        """
        def normalize_scores(values, scale):
            result = []
            for v in values:
                if v >= 0:
                    result.append(v / scale)
            return result
        """,
        """
        def format_labels(names, prefix):
            output = {}
            for name in names:
                if len(name) > 3:
                    output[name] = prefix + name.strip()
            return output
        """,
    ),
]