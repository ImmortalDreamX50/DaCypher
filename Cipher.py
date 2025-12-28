# cipher.py
# -------------------------
# Cipher engine: encoding + decoding
# Numbers output WITHOUT hyphens (e.g., 05 19 16 → 051916)
# -------------------------

import random

ALPH = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# ---------- helpers ----------
def split_numbers(encoded):
    """Split concatenated numbers into integers (assume 2-digit per letter)."""
    s = encoded.strip()
    nums = []
    i = 0
    while i < len(s):
        nums.append(int(s[i:i+2]))
        i += 2
    return nums

def nums_from_word_direct(word):
    return [ALPH.index(ch) + 1 for ch in word]

def wrap_one_to_26(n):
    return ((n - 1) % 26) + 1

def complement_nums(nums):
    return [27 - n for n in nums]

def shift_nums(nums, shift):
    return [wrap_one_to_26(n + shift) for n in nums]

def join_no_dash_2digit(nums):
    return "".join(f"{n:02d}" for n in nums)

# ---------- encoders ----------
def direct_encode(word):
    return join_no_dash_2digit(nums_from_word_direct(word.upper()))

def complement_encode(word):
    base = nums_from_word_direct(word.upper())
    comp = complement_nums(base)
    return join_no_dash_2digit(comp)

def comp_then_shift_encode(word, shift):
    base = nums_from_word_direct(word.upper())
    comp = complement_nums(base)
    shifted = shift_nums(comp, shift)
    return join_no_dash_2digit(shifted)

def math_encode_direct_then_shift(word, shift):
    base = nums_from_word_direct(word.upper())
    shifted = shift_nums(base, shift)
    return join_no_dash_2digit(shifted)

# ---------- decoders ----------
def direct_decode(chunk):
    nums = split_numbers(chunk)
    return "".join(ALPH[n - 1] for n in nums)

def complement_decode(chunk):
    nums = split_numbers(chunk)
    decoded_nums = [27 - n for n in nums]
    return "".join(ALPH[n - 1] for n in decoded_nums)

def comp_then_shift_decode(chunk, shift):
    nums = split_numbers(chunk)
    unshifted = shift_nums(nums, -shift)
    original = [27 - n for n in unshifted]
    return "".join(ALPH[n - 1] for n in original)

def direct_then_shift_decode(chunk, shift):
    nums = split_numbers(chunk)
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
            if mode == 0:
                out.append(direct_encode(w))
            elif mode == 1:
                out.append(complement_encode(w))
            else:
                out.append(comp_then_shift_encode(w, -1))
        return " ".join(out)

    if 20 <= level <= 29:
        for i, w in enumerate(words_list):
            mode = i % 3
            if mode == 0:
                out.append(direct_encode(w))
            elif mode == 1:
                out.append(complement_encode(w))
            else:
                out.append(comp_then_shift_encode(w, -2))
        return " ".join(out)

    # level >= 30
    for i, w in enumerate(words_list):
        mode = i % 3
        if mode == 0:
            out.append(comp_then_shift_encode(w, -2))
        elif mode == 1:
            out.append(comp_then_shift_encode(w, +1))
        else:
            out.append(complement_encode(w))
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
            if mode == 0:
                out.append(direct_decode(c))
            elif mode == 1:
                out.append(complement_decode(c))
            else:
                out.append(comp_then_shift_decode(c, -1))
        return " ".join(out)

    if 20 <= level <= 29:
        for i, c in enumerate(chunks):
            mode = i % 3
            if mode == 0:
                out.append(direct_decode(c))
            elif mode == 1:
                out.append(complement_decode(c))
            else:
                out.append(comp_then_shift_decode(c, -2))
        return " ".join(out)

    # level >= 30
    for i, c in enumerate(chunks):
        mode = i % 3
        if mode == 0:
            out.append(comp_then_shift_decode(c, -2))
        elif mode == 1:
            out.append(comp_then_shift_decode(c, +1))
        else:
            out.append(complement_decode(c))
    return " ".join(out)

def random_shift():
    return random.choice([-2, -1, 1, 2])


