"""
precompute_tanakh.py
====================

This script walks a directory of Sefaria export JSON files (one per book)
and produces a set of per‑chapter JSON files ready for use by the
Tanakh Gematria Browser.  It generalises the functionality of
``precompute_genesis.py`` to handle multiple books at once.

Each input file should be a ``*.json`` export from Sefaria and contain
fields ``title`` and ``text``.  The ``text`` field must be an array
where each element is a chapter (list of verses), and each verse is a
string of Hebrew letters (with or without vowels/cantillation).  Both
``Tanach with Text Only`` and ``Tanach with Ta'amei Hamikra`` formats
work.

For each book the script creates an output directory under the
specified ``out_root`` (e.g. ``dataset/Genesis``, ``dataset/Exodus``).
Within each directory it writes one JSON file per chapter (e.g.
``1.json``, ``2.json``, ...).  The schema matches the output of
``precompute_genesis.py``.

Usage::

    python precompute_tanakh.py --input-dir /path/to/json/Tanakh/Torah/Genesis/Hebrew \
                                --out-dir dataset

If the input directory contains multiple JSON files, the script will
process each of them.  If you want to process a single file you can
use ``--input-file`` instead of ``--input-dir``.
"""

import json
import os
import re
import argparse
from typing import Dict, List

from torahcalc_methods import ADDITIVE_METHODS, DEFAULT_LETTER_NAMES


def remove_diacritics(s: str) -> str:
    """Remove Hebrew vowel points and cantillation marks from a string."""
    return re.sub(r'[\u0591-\u05C7]', '', s)


def letters_only(s: str) -> str:
    """Remove all non‑Hebrew letters from a string."""
    return ''.join(c for c in s if '\u05d0' <= c <= '\u05ea')


def tokenize(verse: str) -> List[str]:
    """Split a verse into tokens on whitespace and maqaf (U+05BE)."""
    verse = verse.replace('\u05c3', '')  # remove sof pasuq
    words = re.split(r'[\s\u05be]+', verse.strip())
    return [w for w in words if w]


def precompute_book(book_json_path: str, out_root: str) -> None:
    """Precompute gematria values for a single Sefaria book JSON file."""
    with open(book_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    title = data.get('title', os.path.basename(book_json_path).split('.')[0])
    text = data.get('text')
    if not isinstance(text, list):
        raise ValueError(f"Unexpected structure in {book_json_path}: 'text' should be a list of chapters")

    book_out_dir = os.path.join(out_root, title)
    os.makedirs(book_out_dir, exist_ok=True)

    for chapter_idx, verses in enumerate(text, start=1):
        chapter_data: Dict[str, Dict] = {}
        for verse_idx, verse in enumerate(verses, start=1):
            original = verse
            # Remove diacritics (if any) and obtain letters‑only string
            cleaned = remove_diacritics(verse)
            letters = letters_only(cleaned)
            tokens = tokenize(cleaned)

            token_entries: List[Dict] = []
            token_totals: Dict[str, int] = {method: 0 for method in ADDITIVE_METHODS.keys()}

            for tok in tokens:
                letters_tok = letters_only(tok)
                values: Dict[str, int] = {}
                for method_name, func in ADDITIVE_METHODS.items():
                    if method_name in {'shemi', 'neelam', 'ofanim'}:
                        # Use default letter names for Milui‑dependent methods
                        values[method_name] = func(letters_tok, DEFAULT_LETTER_NAMES)
                    else:
                        values[method_name] = func(letters_tok)
                    token_totals[method_name] += values[method_name]
                token_entries.append({'t': letters_tok, 'v': values})

            verse_key = str(verse_idx)
            chapter_data[verse_key] = {
                'text': original,
                'text_letters': letters,
                'tokens': [te['t'] for te in token_entries],
                'values': {
                    'sum_of_tokens': token_totals,
                    'tokens': token_entries,
                }
            }

        out_path = os.path.join(book_out_dir, f"{chapter_idx}.json")
        with open(out_path, 'w', encoding='utf-8') as f_out:
            json.dump({title: {str(chapter_idx): chapter_data}}, f_out, ensure_ascii=False, indent=2)
        print(f"Wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Precompute gematria values for Sefaria Tanakh JSON files")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--input-dir', help='Directory containing one or more Sefaria book JSON files')
    group.add_argument('--input-file', help='Path to a single Sefaria book JSON file')
    parser.add_argument('--out-dir', required=True, help='Output root directory for dataset (per book subdirs)')
    args = parser.parse_args()

    if args.input_file:
        precompute_book(args.input_file, args.out_dir)
    else:
        for fname in os.listdir(args.input_dir):
            if fname.lower().endswith('.json'):
                precompute_book(os.path.join(args.input_dir, fname), args.out_dir)


if __name__ == '__main__':
    main()