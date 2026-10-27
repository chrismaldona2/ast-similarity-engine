
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
