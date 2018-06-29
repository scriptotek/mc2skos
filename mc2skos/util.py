def is_uri(value):
    return value.startswith('http://') or value.startswith('https://')


def is_str(obj):
    try:
        return isinstance(obj, basestring)  # Python 2.x
    except NameError:
        return isinstance(obj, str)  # Python 3.x
