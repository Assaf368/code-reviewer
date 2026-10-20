def calc_area(nums, left, right):
    width = right - left
    height = min(nums[left], nums[right])
    return width * height


def max_area(nums: list[int]) -> int:
    """Return the largest amount of water a container can hold.

    nums[i] is the height of a vertical line at position i. A container is
    formed by any two lines together with the x-axis. Its area is the distance
    between the two lines times the height of the shorter one.
    nums has at least two elements.
    """
    best = 0
    calc_area_flag = True
    left, right = 0, len(nums) - 1

    while left < right:
        if calc_area_flag:
            best = max(best, calc_area(nums, left, right))

        if nums[left] >= nums[right]:
            right -= 1
            if nums[right] <= nums[right + 1]:
                calc_area_flag = False
            else:
                calc_area_flag = True
        else:
            left += 1
            if nums[left] <= nums[right - 1]:
                calc_area_flag = False
            else:
                calc_area_flag = True

    return best
