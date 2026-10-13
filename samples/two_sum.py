dict = {}

def registerInDict(index, value):
    dict[value] = index

def getIndex(value):
    return dict[value]

def two_sum(nums, target):
    for i, x in enumerate(nums):
        registerInDict(i, x)
    for x in nums:
        value = target - x
        if value in dict:
            return [getIndex(value), nums.index(x)]