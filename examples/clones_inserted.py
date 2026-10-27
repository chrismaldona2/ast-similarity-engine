
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
