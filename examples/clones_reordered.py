
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
