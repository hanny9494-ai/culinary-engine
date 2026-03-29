#!/usr/bin/env python3
"""
assign_recipe_id.py — Stage 5.6
Assign unique recipe_id to every recipe in stage5_batch output files.

ID format: {book_id}_r{seq:04d}, e.g. ofc_r0001
- book_id = filename stem with '_recipes' removed
- seq starts at 0001 per book, independent numbering
- In-place update; skips recipes that already have a recipe_id
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE5_DIR = ROOT / "output" / "stage5_batch"


def main() -> None:
    recipe_files = sorted(STAGE5_DIR.glob("*_recipes.json"))
    if not recipe_files:
        print(f"No recipe files found in {STAGE5_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(recipe_files)} recipe file(s)")

    total_assigned = 0
    total_skipped = 0
    books_processed = 0

    for rf in recipe_files:
        # Derive book_id: strip trailing '_recipes' from stem
        stem = rf.stem
        if stem.endswith("_recipes"):
            book_id = stem[: -len("_recipes")]
        else:
            book_id = stem

        try:
            text = rf.read_text(encoding="utf-8")
            recipes = json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"  [SKIP] {rf.name}: invalid JSON — {exc}")
            continue
        except Exception as exc:
            print(f"  [ERROR] {rf.name}: {exc}")
            continue

        if not isinstance(recipes, list):
            print(f"  [SKIP] {rf.name}: not a JSON array")
            continue

        seq = 1
        assigned = 0
        skipped = 0

        for recipe in recipes:
            if not isinstance(recipe, dict):
                continue
            existing = recipe.get("recipe_id")
            if existing and isinstance(existing, str) and existing.strip():
                skipped += 1
                seq += 1
                continue
            recipe["recipe_id"] = f"{book_id}_r{seq:04d}"
            seq += 1
            assigned += 1

        if assigned > 0:
            rf.write_text(
                json.dumps(recipes, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        total_assigned += assigned
        total_skipped += skipped
        books_processed += 1
        print(f"  {rf.name}: assigned={assigned}, skipped={skipped}")

    print(
        f"\nDone. books={books_processed}, "
        f"recipes_assigned={total_assigned}, "
        f"recipes_skipped(already had id)={total_skipped}"
    )


if __name__ == "__main__":
    main()
