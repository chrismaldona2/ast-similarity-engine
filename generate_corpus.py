from pathlib import Path

examples_dir = Path("examples")
examples_dir.mkdir(exist_ok=True)

# Same logic, different variable names
(examples_dir / "clones_renamed.py").write_text("""
def average(numbers):
    total = 0
    for n in numbers:
        total += n
    return total / len(numbers)

def mean_value(values):
    acc = 0
    for v in values:
        acc += v
    return acc / len(values)
""", encoding="utf-8")

# Same result, but the independent statements are in a different order
(examples_dir / "clones_reordered.py").write_text("""
def describe_range(data):
    low = min(data)
    high = max(data)
    spread = high - low
    return low, high, spread

def range_info(values):
    high = max(values)
    low = min(values)
    spread = high - low
    return low, high, spread
""", encoding="utf-8")

# Similar logic, with an extra check for None
(examples_dir / "clones_inserted.py").write_text("""
def clean_names(names):
    result = []
    for name in names:
        if name:
            result.append(name.strip().lower())
    return result

def normalize_tags(tags):
    if tags is None:
        return []
    out = []
    for tag in tags:
        if tag:
            out.append(tag.strip().lower())
    return out
""", encoding="utf-8")

# Different functions that shouldn't be considered clones
(examples_dir / "distinct.py").write_text("""
def binary_search(items, target):
    low, high = 0, len(items) - 1
    while low <= high:
        mid = (low + high) // 2
        if items[mid] < target:
            low = mid + 1
        elif items[mid] > target:
            high = mid - 1
        else:
            return mid
    return -1

def is_valid_email(text):
    if "@" not in text:
        return False
    user, _, domain = text.partition("@")
    return bool(user) and "." in domain

def count_words(sentence):
    counts = {}
    for word in sentence.split():
        counts[word] = counts.get(word, 0) + 1
    return counts
""", encoding="utf-8")

# Simple getters that could trigger false positives
(examples_dir / "getters.py").write_text("""
class User:
    def get_name(self):
        return self.name

    def get_email(self):
        return self.email

    def get_age(self):
        return self.age
""", encoding="utf-8")

# Invalid syntax to make sure the tool handles errors gracefully
(examples_dir / "broken.py").write_text("""
def broken(:
    return 1
""", encoding="utf-8")

print("Example corpus created in 'examples/'.")