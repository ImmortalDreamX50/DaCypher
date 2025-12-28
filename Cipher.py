# cipher_fixed.py
import random

ALPH = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# ---------- helpers ----------
def nums_from_word_direct(word):
    return [ALPH.index(ch) + 1 for ch in word]

def wrap_one_to_26(n):
    return ((n - 1) % 26) + 1

def complement_nums(nums):
    return [27 - n for n in nums]

def shift_nums(nums, shift):
    return [wrap_one_to_26(n + shift) for n in nums]

def two_digit(n):
    """Return number as 2-digit string, e.g., 1 -> '01'"""
    return f"{n:02d}"

def join_no_dash_2digit(nums):
    """Join numbers as 2-digit strings concatenated."""
    return "".join(two_digit(n) for n in nums)

# ---------- encoders ----------
def direct_encode(word):
    nums = nums_from_word_direct(word.upper())
    return join_no_dash_2digit(nums)

def complement_encode(word):
    nums = nums_from_word_direct(word.upper())
    comp = complement_nums(nums)
    return join_no_dash_2digit(comp)

def comp_then_shift_encode(word, shift):
    nums = nums_from_word_direct(word.upper())
    comp = complement_nums(nums)
    shifted = shift_nums(comp, shift)
    return join_no_dash_2digit(shifted)

def math_encode_direct_then_shift(word, shift):
    nums = nums_from_word_direct(word.upper())
    shifted = shift_nums(nums, shift)
    return join_no_dash_2digit(shifted)

# ---------- decoders ----------
def split_numbers_2digit(encoded):
    """Split concatenated string into 2-digit numbers."""
    nums = []
    s = encoded.strip()
    for i in range(0, len(s), 2):
        nums.append(int(s[i:i+2]))
    return nums

def direct_decode(chunk):
    nums = split_numbers_2digit(chunk)
    return "".join(ALPH[n - 1] for n in nums)

def complement_decode(chunk):
    nums = split_numbers_2digit(chunk)
    return "".join(ALPH[27 - n - 1] for n in nums)

def comp_then_shift_decode(chunk, shift):
    nums = split_numbers_2digit(chunk)
    unshifted = shift_nums(nums, -shift)
    original = [27 - n for n in unshifted]
    return "".join(ALPH[n - 1] for n in original)

def direct_then_shift_decode(chunk, shift):
    nums = split_numbers_2digit(chunk)
    unshifted = shift_nums(nums, -shift)
    return "".join(ALPH[n - 1] for n in unshifted)

# ---------- high-level encode/decode ----------
def encode_for_level(words_list, level):
    out = []
    if 1 <= level <= 9:
        for i, w in enumerate(words_list):
            out.append(direct_encode(w) if i % 2 == 0 else complement_encode(w))
        return " ".join(out)
    if 10 <= level <= 19:
        for i, w in enumerate(words_list):
            mode = i % 3
            if mode == 0: out.append(direct_encode(w))
            elif mode == 1: out.append(complement_encode(w))
            else: out.append(comp_then_shift_encode(w, -1))
        return " ".join(out)
    if 20 <= level <= 29:
        for i, w in enumerate(words_list):
            mode = i % 3
            if mode == 0: out.append(direct_encode(w))
            elif mode == 1: out.append(complement_encode(w))
            else: out.append(comp_then_shift_encode(w, -2))
        return " ".join(out)
    for i, w in enumerate(words_list):
        mode = i % 3
        if mode == 0: out.append(comp_then_shift_encode(w, -2))
        elif mode == 1: out.append(comp_then_shift_encode(w, +1))
        else: out.append(complement_encode(w))
    return " ".join(out)

def decode_for_level(encoded_text, level):
    chunks = encoded_text.split()
    out = []
    if 1 <= level <= 9:
        for i, c in enumerate(chunks):
            out.append(direct_decode(c) if i % 2 == 0 else complement_decode(c))
        return " ".join(out)
    if 10 <= level <= 19:
        for i, c in enumerate(chunks):
            mode = i % 3
            if mode == 0: out.append(direct_decode(c))
            elif mode == 1: out.append(complement_decode(c))
            else: out.append(comp_then_shift_decode(c, -1))
        return " ".join(out)
    if 20 <= level <= 29:
        for i, c in enumerate(chunks):
            mode = i % 3
            if mode == 0: out.append(direct_decode(c))
            elif mode == 1: out.append(complement_decode(c))
            else: out.append(comp_then_shift_decode(c, -2))
        return " ".join(out)
    for i, c in enumerate(chunks):
        mode = i % 3
        if mode == 0: out.append(comp_then_shift_decode(c, -2))
        elif mode == 1: out.append(comp_then_shift_decode(c, +1))
        else: out.append(complement_decode(c))
    return " ".join(out)

def random_shift():
    return random.choice([-2, -1, 1, 2])
