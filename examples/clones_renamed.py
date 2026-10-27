
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
