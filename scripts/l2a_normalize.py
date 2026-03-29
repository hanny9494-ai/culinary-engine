#!/usr/bin/env python3
"""
l2a_normalize.py — L2a Stage 1
Normalize 18,951 raw ingredient strings to ~3-4k canonical atoms using LLM.

Reads:  output/l2a/ingredient_seeds.json
Writes: output/l2a/canonical_map.json
        output/l2a/normalize_errors.json  (failed batches)

API: qwen-plus via proxy (L0_API_ENDPOINT / L0_API_KEY env vars).
     Falls back to DashScope direct if env vars absent.
Concurrency: up to 4 async requests (Flash supports 3-5 concurrent).
"""

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

try:
    import aiohttp
except ImportError:
    print("aiohttp not installed. Run: pip install aiohttp", file=sys.stderr)
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("tqdm not installed. Run: pip install tqdm", file=sys.stderr)
    sys.exit(1)

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
L2A_DIR = ROOT / "output" / "l2a"

DEFAULT_INPUT = L2A_DIR / "ingredient_seeds.json"
DEFAULT_OUTPUT = L2A_DIR / "canonical_map.json"
ERRORS_OUTPUT = L2A_DIR / "normalize_errors.json"

# ── API config ─────────────────────────────────────────────────────────────────
PROXY_BASE = os.environ.get("L0_API_ENDPOINT", "").strip() or "http://localhost:3001/v1"
PROXY_KEY = os.environ.get("L0_API_KEY", "sk-xxx").strip()
DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_KEY = os.environ.get("DASHSCOPE_API_KEY", "").strip()

MODEL = "qwen-plus"
MAX_CONCURRENCY = 4
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # seconds


def get_api_config() -> tuple[str, str]:
    """Return (base_url, api_key) — proxy first, DashScope fallback."""
    if os.environ.get("L0_API_ENDPOINT"):
        return PROXY_BASE, PROXY_KEY
    if DASHSCOPE_KEY:
        return DASHSCOPE_BASE, DASHSCOPE_KEY
    # Default to proxy even without explicit env
    return PROXY_BASE, PROXY_KEY


SYSTEM_PROMPT = (
    "You are a culinary ingredient normalization expert. "
    "Return only valid JSON, no markdown fences, no explanation."
)

USER_PROMPT_TEMPLATE = """\
Normalize these ingredient strings into canonical atoms.
Rules:
- Merge synonyms (e.g. scallion / green onion / spring onion → scallions)
- Merge singular/plural (tomato/tomatoes → tomato)
- Strip quantity modifiers and prep notes from the canonical name
  (e.g. "2 cloves garlic", "minced garlic" → canonical: garlic)
- Preserve ALL ingredients, even low-frequency rare ones
  (truffle salt, squid ink, black garlic, miso butter = separate canonicals)
- For items whose category is "other", reclassify to the correct category
  (meat/seafood/dairy/vegetable/grain/herb/spice/sauce/oil/fruit/condiment/other)
- canonical_id: lowercase, underscores, ASCII only (e.g. "garlic", "soy_sauce")
- canonical_name_zh: provide best Chinese culinary translation
- confidence: "high" if obvious, "medium" if plausible, "low" if uncertain

Return a JSON object with exactly this structure (no other keys):
{{
  "canonicals": [
    {{
      "canonical_id": "garlic",
      "canonical_name_en": "garlic",
      "canonical_name_zh": "蒜",
      "category": "vegetable",
      "confidence": "high",
      "raw_variants": ["garlic", "garlic cloves", "minced garlic"]
    }}
  ],
  "mapping": {{
    "garlic": "garlic",
    "garlic cloves": "garlic",
    "minced garlic": "garlic"
  }}
}}

Ingredients to normalize (format: raw_string | frequency):
{items_block}
"""


def build_items_block(batch: list[dict]) -> str:
    lines = [f"{entry['item']} | {entry['frequency']}" for entry in batch]
    return "\n".join(lines)


async def call_llm(
    session: aiohttp.ClientSession,
    base_url: str,
    api_key: str,
    prompt_user: str,
    semaphore: asyncio.Semaphore,
) -> dict | None:
    """Call LLM API and return parsed JSON response dict, or None on failure."""
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_user},
        ],
        "temperature": 0.1,
        "max_tokens": 8192,
    }

    async with semaphore:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise RuntimeError(f"HTTP {resp.status}: {body[:200]}")
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    # Strip markdown fences if present
                    content = content.strip()
                    if content.startswith("```"):
                        lines = content.split("\n")
                        content = "\n".join(lines[1:-1])
                    return json.loads(content)
            except Exception as exc:
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * attempt)
                else:
                    return {"_error": str(exc)}
    return None


def merge_batch_result(
    result: dict,
    batch: list[dict],
    all_canonicals: dict,  # canonical_id -> canonical dict
    raw_to_canonical: dict,
) -> list[dict]:
    """Merge a single batch LLM result into global maps. Returns unmapped items."""
    unmapped = []
    mapping: dict[str, str] = result.get("mapping", {})
    canonicals_list: list[dict] = result.get("canonicals", [])

    # Index new canonicals
    for c in canonicals_list:
        cid = c.get("canonical_id", "").strip()
        if not cid:
            continue
        if cid not in all_canonicals:
            all_canonicals[cid] = {
                "canonical_id": cid,
                "canonical_name_en": c.get("canonical_name_en", cid),
                "canonical_name_zh": c.get("canonical_name_zh", ""),
                "category": c.get("category", "other"),
                "confidence": c.get("confidence", "medium"),
                "raw_variants": list(c.get("raw_variants", [])),
                "external_ids": {},
            }
        else:
            # Merge raw_variants
            existing_variants = set(all_canonicals[cid]["raw_variants"])
            for rv in c.get("raw_variants", []):
                existing_variants.add(rv)
            all_canonicals[cid]["raw_variants"] = sorted(existing_variants)

    # Apply mapping
    for entry in batch:
        raw = entry["item"]
        cid = mapping.get(raw)
        if cid:
            raw_to_canonical[raw] = cid
            # Ensure raw_variant is recorded
            if cid in all_canonicals and raw not in all_canonicals[cid]["raw_variants"]:
                all_canonicals[cid]["raw_variants"].append(raw)
        else:
            unmapped.append(entry)

    return unmapped


async def process_all_batches(
    batches: list[tuple[str, list[dict]]],
    base_url: str,
    api_key: str,
    dry_run: bool,
) -> tuple[dict, dict, list[dict]]:
    all_canonicals: dict[str, Any] = {}
    raw_to_canonical: dict[str, str] = {}
    errors: list[dict] = []

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    connector = aiohttp.TCPConnector(trust_env=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for cat, batch in batches:
            prompt = USER_PROMPT_TEMPLATE.format(items_block=build_items_block(batch))
            tasks.append((cat, batch, call_llm(session, base_url, api_key, prompt, semaphore)))

        pbar = tqdm(total=len(tasks), desc="Normalizing batches", unit="batch")

        futures = [(cat, batch, asyncio.ensure_future(coro)) for cat, batch, coro in tasks]

        for cat, batch, fut in futures:
            result = await fut
            pbar.update(1)

            if result is None or "_error" in result:
                err_msg = (result or {}).get("_error", "null response")
                errors.append({
                    "category": cat,
                    "batch_size": len(batch),
                    "items_sample": [e["item"] for e in batch[:5]],
                    "error": err_msg,
                })
                tqdm.write(f"  [FAIL] category={cat} size={len(batch)}: {err_msg[:80]}")
            else:
                unmapped = merge_batch_result(result, batch, all_canonicals, raw_to_canonical)
                if unmapped:
                    tqdm.write(
                        f"  [WARN] category={cat}: {len(unmapped)} items unmapped by LLM"
                    )

            if dry_run:
                pbar.close()
                break

        pbar.close()

    return all_canonicals, raw_to_canonical, errors


def chunk_list(lst: list, size: int) -> list[list]:
    return [lst[i : i + size] for i in range(0, len(lst), size)]


def build_batches(
    ingredients: list[dict], batch_size: int, resume_categories: set[str]
) -> list[tuple[str, list[dict]]]:
    """Group by category, chunk each group into batches."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for ing in ingredients:
        cat = ing.get("category_guess", "other")
        groups[cat].append(ing)

    batches = []
    for cat, items in sorted(groups.items()):
        if cat in resume_categories:
            continue
        for chunk in chunk_list(items, batch_size):
            batches.append((cat, chunk))

    return batches


def load_resume_state(output_path: Path) -> tuple[dict, dict, set[str]]:
    """Load existing canonical_map.json for --resume mode."""
    if not output_path.exists():
        return {}, {}, set()
    try:
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        all_canonicals = {c["canonical_id"]: c for c in existing.get("canonicals", [])}
        raw_to_canonical = existing.get("raw_to_canonical", {})
        done_cats: set[str] = set()
        for c in all_canonicals.values():
            done_cats.add(c.get("category", "other"))
        return all_canonicals, raw_to_canonical, done_cats
    except Exception as exc:
        print(f"[WARN] Could not load existing output for resume: {exc}", file=sys.stderr)
        return {}, {}, set()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize ingredient seeds to canonical L2a atoms."
    )
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help=f"Path to ingredient_seeds.json (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Path to canonical_map.json (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument("--batch-size", type=int, default=200, help="Items per LLM batch (default: 200)")
    parser.add_argument("--dry-run", action="store_true", help="Process first batch only, print result")
    parser.add_argument("--resume", action="store_true", help="Skip categories already processed")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading seeds from {args.input} ...")
    seeds_data = json.loads(args.input.read_text(encoding="utf-8"))
    ingredients: list[dict] = seeds_data.get("ingredients", [])
    total_raw = len(ingredients)
    print(f"Total raw ingredients: {total_raw}")

    base_url, api_key = get_api_config()
    print(f"API endpoint: {base_url}, model: {MODEL}")

    all_canonicals: dict[str, Any] = {}
    raw_to_canonical: dict[str, str] = {}
    resume_categories: set[str] = set()
    if args.resume:
        all_canonicals, raw_to_canonical, resume_categories = load_resume_state(args.output)
        if resume_categories:
            print(f"Resuming — skipping categories: {sorted(resume_categories)}")

    batches = build_batches(ingredients, args.batch_size, resume_categories)
    print(f"Batches to process: {len(batches)}")

    if args.dry_run:
        print("[DRY RUN] Processing first batch only ...")

    t0 = time.time()
    new_canonicals, new_raw_map, errors = asyncio.run(
        process_all_batches(batches, base_url, api_key, dry_run=args.dry_run)
    )

    # Merge with resumed state
    for cid, cdata in new_canonicals.items():
        if cid not in all_canonicals:
            all_canonicals[cid] = cdata
        else:
            existing_variants = set(all_canonicals[cid]["raw_variants"])
            for rv in cdata.get("raw_variants", []):
                existing_variants.add(rv)
            all_canonicals[cid]["raw_variants"] = sorted(existing_variants)
    raw_to_canonical.update(new_raw_map)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Canonical atoms: {len(all_canonicals)}")
    print(f"  Mapped: {len(raw_to_canonical)} / {total_raw}")
    print(f"  Failed batches: {len(errors)}")

    if args.dry_run:
        print("\n[DRY RUN] Preview:")
        print(json.dumps(
            {"canonicals": list(all_canonicals.values())[:3],
             "mapping_sample": dict(list(raw_to_canonical.items())[:10])},
            ensure_ascii=False, indent=2))
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    canonical_map = {
        "metadata": {
            "total_raw": total_raw,
            "total_canonical": len(all_canonicals),
            "model": MODEL,
            "created": str(date.today()),
            "unmapped_count": total_raw - len(raw_to_canonical),
            "failed_batches": len(errors),
        },
        "canonicals": sorted(all_canonicals.values(), key=lambda c: c["canonical_id"]),
        "raw_to_canonical": dict(sorted(raw_to_canonical.items())),
    }

    args.output.write_text(
        json.dumps(canonical_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Written: {args.output}")

    if errors:
        ERRORS_OUTPUT.write_text(
            json.dumps({"errors": errors}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Errors written: {ERRORS_OUTPUT}")


if __name__ == "__main__":
    main()
