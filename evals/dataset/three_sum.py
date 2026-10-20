def three_sum(nums: list[int], target: int) -> list[list[int]]:
    """Return all unique triplets of values from nums that sum to target.

    Each triplet uses three different positions in nums. The result must not
    contain the same triplet twice. The order of the triplets, and of the
    values inside each triplet, does not matter.
    """
    results = []
    nums.sort()
    for i in range(len(nums)):
        if i > 0 and nums[i] == nums[i - 1]:
            continue
        left, right = i + 1, len(nums) - 1

        while left < right:
            if nums[left] + nums[right] + nums[i] == target:
                results.append([nums[left], nums[right], nums[i]])
                left += 1
                right -= 1
            elif nums[left] + nums[right] + nums[i] > target:
                right -= 1
            else:
                left += 1

    return results
