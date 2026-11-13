"""JSON behavior equality shared by transport parity and package qualification."""
from fractions import Fraction
import math

_ABS_TOLERANCE = Fraction(1e-9)


def outputs_equal(left, right) -> bool:
    """Compare JSON kinds and exact integers, tolerating finite float noise."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if any(isinstance(value, float) and not math.isfinite(value) for value in (left, right)):
            return False
        if isinstance(left, int) and isinstance(right, int):
            return left == right
        # Converting an integer to float before subtraction can hide a changed
        # value above 2**53, or overflow for otherwise valid JSON integers.
        return abs(Fraction(left) - Fraction(right)) < _ABS_TOLERANCE
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(outputs_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(outputs_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, str) and isinstance(right, str):
        return left == right
    return left is None and right is None
