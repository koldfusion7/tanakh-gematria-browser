"""
torahcalc_methods.py
=====================

This module implements a variety of gematria calculation methods based on
the descriptions from TorahCalc's "Explanations of Gematria Methods with
Charts".  It exposes functions to compute per‑letter values, word sums
and simple transformations required by those methods.  The aim is to
match the values displayed on TorahCalc (e.g. for the word "בראשית").

Only additive methods (those where the result for a string is the sum of
per‑letter contributions) are implemented here.  Phrase‑dependent methods
such as Kolel or Musafi should be computed at runtime in the client by
summing the results of the additive methods and then applying the
appropriate adjustment (e.g. adding the number of letters).

The functions in this module return integers.  They accept strings
containing Hebrew letters (optionally with vowel/cantillation marks) and
ignore any non‑Hebrew characters.  Final forms are normalised to their
base forms for the purposes of the value lookup.
"""

import re
from typing import Dict, List

# -----------------------------------------------------------------------------
# Basic lookup tables
# -----------------------------------------------------------------------------

# Standard (Mispar Hechrachi) values for the 22 letters plus final forms.
_HECHRACHI: Dict[str, int] = {
    'א': 1, 'ב': 2, 'ג': 3, 'ד': 4, 'ה': 5, 'ו': 6, 'ז': 7, 'ח': 8, 'ט': 9,
    'י': 10, 'כ': 20, 'ך': 20, 'ל': 30, 'מ': 40, 'ם': 40, 'נ': 50, 'ן': 50,
    'ס': 60, 'ע': 70, 'פ': 80, 'ף': 80, 'צ': 90, 'ץ': 90, 'ק': 100, 'ר': 200,
    'ש': 300, 'ת': 400,
}

# Large (Gadol / Sofit) values for final letters.  Non‑final letters map to
# their Hechrachi values.
_GADOL: Dict[str, int] = {
    'א': 1, 'ב': 2, 'ג': 3, 'ד': 4, 'ה': 5, 'ו': 6, 'ז': 7, 'ח': 8, 'ט': 9,
    'י': 10, 'כ': 20, 'ל': 30, 'מ': 40, 'נ': 50, 'ס': 60, 'ע': 70, 'פ': 80,
    'צ': 90, 'ק': 100, 'ר': 200, 'ש': 300, 'ת': 400,
    # Finals map to 500..900
    'ך': 500, 'ם': 600, 'ן': 700, 'ף': 800, 'ץ': 900,
}

# Ordinal (Siduri) values – 1 through 22.  Final forms map to the same
# ordinal as their regular form.
_SIDURI: Dict[str, int] = {
    'א': 1, 'ב': 2, 'ג': 3, 'ד': 4, 'ה': 5, 'ו': 6, 'ז': 7, 'ח': 8, 'ט': 9,
    'י': 10, 'כ': 11, 'ך': 11, 'ל': 12, 'מ': 13, 'ם': 13, 'נ': 14, 'ן': 14,
    'ס': 15, 'ע': 16, 'פ': 17, 'ף': 17, 'צ': 18, 'ץ': 18, 'ק': 19, 'ר': 20,
    'ש': 21, 'ת': 22,
}

# Reduced (Katan) values: take the standard value modulo 9 and map 0→9.
# This mapping is defined explicitly to avoid modulo operations at runtime.
_KATAN: Dict[str, int] = {
    'א': 1, 'ב': 2, 'ג': 3, 'ד': 4, 'ה': 5, 'ו': 6, 'ז': 7, 'ח': 8, 'ט': 9,
    'י': 1, 'כ': 2, 'ך': 2, 'ל': 3, 'מ': 4, 'ם': 4, 'נ': 5, 'ן': 5,
    'ס': 6, 'ע': 7, 'פ': 8, 'ף': 8, 'צ': 9, 'ץ': 9, 'ק': 1, 'ר': 2,
    'ש': 3, 'ת': 4,
}

# Mispar Mispari values for each letter.  These values correspond to
# spelled‑out number names as given on TorahCalc.  They are relatively
# large numbers and differ widely between letters.
_MISPARI: Dict[str, int] = {
    'א': 13, 'ב': 760, 'ג': 13, 'ד': 434, 'ה': 38, 'ו': 42, 'ז': 67,
    'ח': 68, 'ט': 419, 'י': 570, 'כ': 100, 'ך': 100, 'ל': 74, 'מ': 80,
    'ם': 80, 'נ': 106, 'ן': 106, 'ס': 60, 'ע': 130, 'פ': 81, 'ף': 81,
    'צ': 104, 'ץ': 104, 'ק': 186, 'ר': 501, 'ש': 1083, 'ת': 720,
}

# Letter names for Milui/Shemi and Ne'elam.  These are the default spellings
# used on TorahCalc.  Alternative spellings may be provided by the UI and
# passed into the milui/neelam/ofanim functions at runtime.
DEFAULT_LETTER_NAMES: Dict[str, str] = {
    'א': 'אלף',
    'ב': 'בית',
    'ג': 'גימל',
    'ד': 'דלת',
    'ה': 'הא',
    'ו': 'וו',
    'ז': 'זין',
    'ח': 'חית',
    'ט': 'טית',
    'י': 'יוד',
    'כ': 'כף', 'ך': 'כף',
    'ל': 'למד',
    'מ': 'מם', 'ם': 'מם',
    'נ': 'נון', 'ן': 'נון',
    'ס': 'סמך',
    'ע': 'עין',
    'פ': 'פא', 'ף': 'פא',
    'צ': 'צדי', 'ץ': 'צדי',
    'ק': 'קוף',
    'ר': 'ריש',
    'ש': 'שן',
    'ת': 'תו',
}

# For Kidmi: cumulative sums of Hechrachi values from Alef up to each letter.
_ORDERED_LETTERS = ['א','ב','ג','ד','ה','ו','ז','ח','ט','י','כ','ל','מ','נ','ס','ע','פ','צ','ק','ר','ש','ת']
_CUM_SUM_HECHRACHI: Dict[str, int] = {}
_running = 0
for ch in _ORDERED_LETTERS:
    _running += _HECHRACHI[ch]
    _CUM_SUM_HECHRACHI[ch] = _running

def _strip_non_hebrew(s: str) -> str:
    """Remove all non‑Hebrew letters from the input string."""
    return ''.join(c for c in s if c in _HECHRACHI)

def _apply_table(s: str, table: Dict[str, int]) -> int:
    """Sum values from a table for the letters of a string, ignoring missing keys."""
    total = 0
    for c in s:
        total += table.get(c, 0)
    return total

# -----------------------------------------------------------------------------
# Public methods
# -----------------------------------------------------------------------------

def mispar_hechrachi(s: str) -> int:
    """Standard gematria (Mispar Hechrachi)."""
    return _apply_table(_strip_non_hebrew(s), _HECHRACHI)

def mispar_gadol(s: str) -> int:
    """Large sofit values for final letters."""
    return _apply_table(_strip_non_hebrew(s), _GADOL)

def mispar_siduri(s: str) -> int:
    """Ordinal values 1..22."""
    return _apply_table(_strip_non_hebrew(s), _SIDURI)

def mispar_katan(s: str) -> int:
    """Reduced values (mod 9 with 0→9)."""
    return _apply_table(_strip_non_hebrew(s), _KATAN)

def mispar_perati(s: str) -> int:
    """HaMerubah HaPerati – sum of squares of Hechrachi values."""
    s = _strip_non_hebrew(s)
    return sum(_HECHRACHI[c] ** 2 for c in s)

def mispar_meshulash(s: str) -> int:
    """Mispar Meshulash – sum of cubes of Hechrachi values."""
    s = _strip_non_hebrew(s)
    return sum(_HECHRACHI[c] ** 3 for c in s)

def mispar_kidmi(s: str) -> int:
    """Mispar Kidmi – cumulative sums of standard values up to each letter."""
    total = 0
    for c in _strip_non_hebrew(s):
        base = c
        # treat final forms as their base character for cumulative sum
        if c in {'ך','כ'}:
            base = 'כ'
        elif c in {'ם','מ'}:
            base = 'מ'
        elif c in {'ן','נ'}:
            base = 'נ'
        elif c in {'ף','פ'}:
            base = 'פ'
        elif c in {'ץ','צ'}:
            base = 'צ'
        total += _CUM_SUM_HECHRACHI.get(base, 0)
    return total

def mispar_boneh(s: str) -> int:
    """Mispar Bone'eh – cumulative sum within a word (building)."""
    total = 0
    running = 0
    for c in _strip_non_hebrew(s):
        running += _HECHRACHI.get(c, 0)
        total += running
    return total

def mispar_mispari(s: str) -> int:
    """Mispar Mispari – per‑letter values from the spelled number names table."""
    return _apply_table(_strip_non_hebrew(s), _MISPARI)

# -----------------------------------------------------------------------------
# Letter substitutions (temurot)
# -----------------------------------------------------------------------------

# Build substitution maps for various ciphers.  Final forms map via their base
# character, then the result is converted back to the appropriate form only
# if it is the same position in the alphabet.  Simplicity: we normalise
# finals to bases, perform substitution, then output only base forms.

# Atbash: reverse the 22‑letter alphabet ( א↔ת, ב↔ש, … ).
_ATBASH_MAP: Dict[str, str] = {}
atbash_pairs = list(zip(_ORDERED_LETTERS, reversed(_ORDERED_LETTERS)))
for a, b in atbash_pairs:
    _ATBASH_MAP[a] = b
    _ATBASH_MAP[b] = a

# Albam: first 11 letters ↔ last 11.  Mapping is 1→12, 2→13, …, 11→22.
_ALBAM_MAP: Dict[str, str] = {}
for i in range(11):
    a = _ORDERED_LETTERS[i]
    b = _ORDERED_LETTERS[i + 11]
    _ALBAM_MAP[a] = b
    _ALBAM_MAP[b] = a

# AchBi: reverse within each half (1–11, 12–22).
_ACHBI_MAP: Dict[str, str] = {}
first_half = _ORDERED_LETTERS[:11]
second_half = _ORDERED_LETTERS[11:]
for half in (first_half, second_half):
    for i, a in enumerate(half):
        b = half[::-1][i]
        _ACHBI_MAP[a] = b

# AtBach: three groups of 9 letters using a 27‑letter sequence (22 letters + 5 finals).
# TorahCalc groups the letters as follows:
#   Group 1: א ב ג ד ה ו ז ח ט
#   Group 2: י כ ל מ נ ס ע פ צ
#   Group 3: ק ר ש ת ך ם ן ף ץ
_ATBACH_MAP: Dict[str, str] = {}
_ATBACH_SEQ = [
    'א','ב','ג','ד','ה','ו','ז','ח','ט',
    'י','כ','ל','מ','נ','ס','ע','פ','צ',
    'ק','ר','ש','ת','ך','ם','ן','ף','ץ'
]
for i in range(0, 27, 9):
    group = _ATBACH_SEQ[i:i+9]
    for j, a in enumerate(group):
        b = group[::-1][j]
        _ATBACH_MAP[a] = b

# Ayak Bachar: same 3×9 groups, rotate each letter to the next group (1→2→3→1).
_AYAK_MAP: Dict[str, str] = {}
groups = [_ATBACH_SEQ[i:i+9] for i in range(0, 27, 9)]
for idx, group in enumerate(groups):
    next_group = groups[(idx + 1) % len(groups)]
    for a, b in zip(group, next_group):
        _AYAK_MAP[a] = b

# Achas Beta: split into 7,7,8 groups and rotate cyclically 1→2→3→1.
_ACHAS_BETA_MAP: Dict[str, str] = {}
_ACHAS_SEQ = ['א','ב','ג','ד','ה','ו','ז',  # 7
               'ח','ט','י','כ','ל','מ','נ',  # 7
               'ס','ע','פ','צ','ק','ר','ש','ת']  # 8
g1 = _ACHAS_SEQ[0:7]
g2 = _ACHAS_SEQ[7:14]
g3 = _ACHAS_SEQ[14:]
for a, b in zip(g1, g2):
    _ACHAS_BETA_MAP[a] = b
for a, b in zip(g2, g3):
    _ACHAS_BETA_MAP[a] = b
for a, b in zip(g3, g1):
    _ACHAS_BETA_MAP[a] = b

# Avgad: shift forward by one letter (wrap around at end of alphabet).  Use
# standard 22‑letter sequence.  Reverse Avgad shifts backward by one.
_AVGAD_MAP: Dict[str, str] = {}
_REV_AVGAD_MAP: Dict[str, str] = {}
for i, a in enumerate(_ORDERED_LETTERS):
    b = _ORDERED_LETTERS[(i + 1) % len(_ORDERED_LETTERS)]
    _AVGAD_MAP[a] = b
    _REV_AVGAD_MAP[b] = a  # reverse mapping

def _transform(s: str, mapping: Dict[str, str]) -> str:
    """Apply a letter substitution mapping to a string of Hebrew letters."""
    out = []
    for c in s:
        base = c
        # normalise finals to their base for mapping
        if c in {'ך','כ'}:
            base = 'כ'
        elif c in {'ם','מ'}:
            base = 'מ'
        elif c in {'ן','נ'}:
            base = 'נ'
        elif c in {'ף','פ'}:
            base = 'פ'
        elif c in {'ץ','צ'}:
            base = 'צ'
        out.append(mapping.get(base, base))
    return ''.join(out)

def atbash_value(s: str) -> int:
    return mispar_hechrachi(_transform(_strip_non_hebrew(s), _ATBASH_MAP))

def albam_value(s: str) -> int:
    return mispar_hechrachi(_transform(_strip_non_hebrew(s), _ALBAM_MAP))

def achbi_value(s: str) -> int:
    return mispar_hechrachi(_transform(_strip_non_hebrew(s), _ACHBI_MAP))

def atbach_value(s: str) -> int:
    """
    AtBach temurah value.  The AtBach transformation maps each letter
    into its partner within the 27‑letter (22 letters plus 5 finals)
    sequence split into three groups of nine, reversed within each
    group.  After applying the mapping we compute the large (Gadol)
    value of the resulting string so that final forms take their
    elevated values (e.g. ף=800).  This matches TorahCalc where
    "בראשית" yields 2207.
    """
    transformed = _transform(_strip_non_hebrew(s), _ATBACH_MAP)
    # Use mispar_gadol to assign large values to any final letters in the result
    return mispar_gadol(transformed)

def ayak_bachar_value(s: str) -> int:
    """
    Ayak Bachar temurah value.  The Ayak Bachar transformation rotates
    each of the three 9‑letter groups (with finals) forward one group
    (group1→group2→group3→group1).  As with AtBach we then compute
    Mispar Gadol on the transformed string so that final forms receive
    their large sofit values.  This produces, for example, 139 for
    "בראשית".
    """
    transformed = _transform(_strip_non_hebrew(s), _AYAK_MAP)
    return mispar_gadol(transformed)

def achas_beta_value(s: str) -> int:
    return mispar_hechrachi(_transform(_strip_non_hebrew(s), _ACHAS_BETA_MAP))

def avgad_value(s: str) -> int:
    return mispar_hechrachi(_transform(_strip_non_hebrew(s), _AVGAD_MAP))

def reverse_avgad_value(s: str) -> int:
    return mispar_hechrachi(_transform(_strip_non_hebrew(s), _REV_AVGAD_MAP))

# -----------------------------------------------------------------------------
# Milui‑dependent methods
# -----------------------------------------------------------------------------

def mispar_shemi(s: str, letter_names: Dict[str, str] = None) -> int:
    """Mispar Shemi (Milui) – sum of Hechrachi values of letter names."""
    if letter_names is None:
        letter_names = DEFAULT_LETTER_NAMES
    total = 0
    for c in _strip_non_hebrew(s):
        name = letter_names.get(c, '')
        total += mispar_hechrachi(name)
    return total

def mispar_neelam(s: str, letter_names: Dict[str, str] = None) -> int:
    """Mispar Ne'elam – sum of Hechrachi values of the hidden parts of the
    letter names (i.e. letter names without the first letter)."""
    if letter_names is None:
        letter_names = DEFAULT_LETTER_NAMES
    total = 0
    for c in _strip_non_hebrew(s):
        name = letter_names.get(c, '')
        hidden = name[1:] if len(name) > 1 else ''
        total += mispar_hechrachi(hidden)
    return total

def ofanim_value(s: str, letter_names: Dict[str, str] = None) -> int:
    """Ofanim – sum of Hechrachi values of the final letter of each letter name."""
    if letter_names is None:
        letter_names = DEFAULT_LETTER_NAMES
    total = 0
    for c in _strip_non_hebrew(s):
        name = letter_names.get(c, '')
        if name:
            total += mispar_hechrachi(name[-1])
    return total

# Expose a list of all additive method functions for convenience.
ADDITIVE_METHODS = {
    'hechrachi': mispar_hechrachi,
    'gadol': mispar_gadol,
    'siduri': mispar_siduri,
    'katan': mispar_katan,
    'perati': mispar_perati,
    'meshulash': mispar_meshulash,
    'kidmi': mispar_kidmi,
    'boneh': mispar_boneh,
    'mispari': mispar_mispari,
    'shemi': mispar_shemi,
    'neelam': mispar_neelam,
    'ofanim': ofanim_value,
    'atbash': atbash_value,
    'albam': albam_value,
    'achbi': achbi_value,
    'atbach': atbach_value,
    'ayak_bachar': ayak_bachar_value,
    'achas_beta': achas_beta_value,
    'avgad': avgad_value,
    'reverse_avgad': reverse_avgad_value,
}