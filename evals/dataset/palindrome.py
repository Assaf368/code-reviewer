def is_palindrome(word: str) -> bool:
    """Return True if word reads the same forward and backward.

    Only letters and digits are considered, and case is ignored. All other
    characters, such as spaces and punctuation, are skipped. A string with
    no letters or digits counts as a palindrome.
    """
    left_index, right_index = 0, len(word) - 1

    while left_index < right_index:
        left_char = word[left_index]
        right_char = word[right_index]

        while not left_char.isalnum():
            if left_index >= right_index:
                return False
            left_index += 1
            left_char = word[left_index]

        while not right_char.isalnum():
            if left_index >= right_index:
                return False
            right_index -= 1
            right_char = word[right_index]

        if left_char.lower() != right_char.lower():
            return False

        left_index += 1
        right_index -= 1

    return True
