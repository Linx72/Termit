def page_bounds(page: int, size: int, total: int) -> tuple[int, int]:
    start = max(0, page * size)
    end = min(total, start + size)
    return start, end + 1
