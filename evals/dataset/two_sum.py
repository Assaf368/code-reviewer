def registerInDict(dict, index, value):
    dict[value] = index


def getIndex(dict, value):
    return dict[value]


def two_sum(nums: list[int], target: int) -> list[int]:
    """Return the indices [i, j] of two different positions whose values sum to target.

    i is smaller than j. If several pairs exist, any one of them is fine.
    If no pair exists, return an empty list.
    """
    result = []
    dict = {}

    for i, x in enumerate(nums):
        value = target - x
        if value in dict:
            result = [getIndex(dict, value), i]
            break
        else:
            registerInDict(dict, i, x)

    return result
