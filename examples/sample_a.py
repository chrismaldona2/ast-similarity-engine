def top_level(x):
    def inner(y):
        return y + 1
    return inner(x)


class Cart:
    def add(self, item):
        self.items.append(item)

    async def fetch(self):
        return 1