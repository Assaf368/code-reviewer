def product_except_self(nums: list[int]) -> list[int]:
    """Return a list where element i is the product of all of nums except nums[i].

    Division must not be used. nums has at least two elements.
    """
    left_results = [] * len(nums)
    right_reuslts = [] * len(nums)
    results = [] * len(nums)

    for i, num in enumerate(nums):
        if i == 0:
            continue
        left_results[i] = left_results[i - 1] * nums[i - 1]

    for i in range(len(nums) - 1, -1, -1):
        if i == len(nums):
            continue
        else:
            right_reuslts[i] = right_reuslts[i + 1] * nums[i + 1]

    for i in range(len(nums)):
        results[i] = left_results[i] * right_reuslts[i]

    return results
