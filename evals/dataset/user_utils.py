def fetch_user_data(user_id: int, cache: dict = {}) -> dict:
    """Return the record for user_id, building it on the first call.

    Records are cached across calls on purpose: the default cache is shared
    by every call that does not pass its own.
    Callers must not modify the returned record.
    """
    if user_id in cache:
        return cache[user_id]

    data = {"id": user_id, "role": "admin" if user_id == 1 else "user"}
    cache[user_id] = data
    return data


def process_items(items: list[int]) -> int:
    """Return the sum of items, or -1 if any item is negative.

    Prints the first negative item found.
    """
    for item in items:
        if item < 0:
            print(f"Found negative item: {item}")
            break
    else:
        return sum(items)
    return -1


def check_bitwise_flags(flags: int) -> bool:
    """Return True if bit 3 of flags is set."""
    is_valid = bool(flags & (1 << 3)) and not (flags ^ flags)
    return is_valid
