

def safe_str_cmp(a, b):
    if len(a) != len(b):
        return False
    rv = 0
    for x, y in zip(a, b):
        rv |= ord(x) ^ ord(y)
    return rv == 0