from __future__ import annotations

import sys


def factorial(n: int) -> int:
    """Calculate factorial of n recursively.

    Args:
        n: A non-negative integer.

    Returns:
        The factorial of n (n!).

    Raises:
        ValueError: If n is negative.
        RecursionError: If n is too large for Python's recursion limit.
    """
    if n < 0:
        raise ValueError(f"Factorial is not defined for negative numbers, got {n}")
    if n == 0:
        return 1
    return n * factorial(n - 1)


# --------------------------------------------------------------------------- #
# Example usage
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    # Small numbers — clear output
    for i in range(11):
        print(f"{i}! = {factorial(i)}")

    # Safe check for large input
    n = 1000
    sys.setrecursionlimit(max(sys.getrecursionlimit(), n + 10))
    try:
        result = factorial(n)
        print(f"\n{n}! computed successfully ({len(str(result))} digits)")
    except RecursionError:
        print(f"\n{n}! exceeded recursion depth — try an iterative approach for very large n")
