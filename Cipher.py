# cipher.py
# -------------------------
# Cipher engine: encoding + decoding
# Updated: numbers output WITHOUT hyphens (e.g., 2085 instead of 20-8-5)
# -------------------------

import random
ALPH = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def split_numbers(encoded):
    """
    Accepts:
      - "15121215"
      - "1-5-12-12-15"
    Returns list of ints.
    """
    if "-" in encoded:
        try:
            return [int(x) for x in encoded.split("-") if x.strip().isdigit()]
        except:
            pass

    numbers = []
    i = 0
    s = encoded.strip()
    while i < len(s):
        if i + 1 < len(s):
            two = int(s[i:i+2])
            if 1 <= two <= 26:
                numbers.append(two)
                i += 2
                continue
        numbers.append(int(s[i]))
        i += 1
    return numbers

# ---------- helpers ----------
def nums_from_word_direct(word):
    return [ALPH.index(ch) + 1 for ch in word]

def join_no_dash(nums):
    """Return numbers concatenated with no hyphens."""
    return "".join(str(n) for n in nums)

def wrap_one_to_26(n):
    return ((n - 1) % 26) + 1

def complement_nums(nums):
    return [27 - n for n in nums]

def shift_nums(nums, shift):
    return [wrap_one_to_26(n + shift) for n in nums]

# ---------- encoders (NO HYPHENS) ----------
def direct_encode(word):
    return join_no_dash(nums_from_word_direct(word.upper()))

def complement_encode(word):
    base = nums_from_word_direct(word.upper())
    return join_no_dash(complement_nums(base))

def comp_then_shift_encode(word, shift):
    base = nums_from_word_direct(word.upper())
    comp = complement_nums(base)
    shifted = shift_nums(comp, shift)
    return join_no_dash(shifted)

def math_encode_direct_then_shift(word, shift):
    base = nums_from_word_direct(word.upper())
    shifted = shift_nums(base, shift)
    return join_no_dash(shifted)

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
