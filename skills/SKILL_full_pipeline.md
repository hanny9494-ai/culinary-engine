# Full Pipeline Skill

## Purpose
Use this workflow to run one book through the full extraction pipeline:

`Stage 1 -> Stage 2 -> Stage 3 -> Stage 3B`

The orchestration entrypoint is `scripts/run_book.py`. It invokes each stage as a subprocess, enforces quality gates after every step, and writes a run summary to `output_root/run_report.json`.

## Flow
```text
book config + API config + question master
    |
    v
Stage 1: source book -> chunks_smart.json
    |
    v
Stage 2: questions x discovered chunks -> question_chunk_matches.json
    |
    v
Stage 3: matches + merged chunks -> l0_principles.jsonl
    |
    v
Stage 3B: l0_principles.jsonl + matches -> l0_principles_v2.jsonl
```

## Inputs And Outputs

### Stage 1
- Inputs: `--book-id`, `config/books.yaml`, `config/api.yaml`, optional TOC JSON such as `config/mc_toc.json`
- Output: `<output_root>/<book_id>/stage1/chunks_smart.json`
- Gate: output file exists and contains at least one chunk

### Stage 2
- Inputs: discovered `*/stage1/chunks_smart.json`, `data/l0_question_master.json`
- Output: `<output_root>/stage2/question_chunk_matches.json`
- Gate: output exists and contains match rows
- Warning threshold: `match_rate <= 0.8`

### Stage 3
- Inputs: Stage 2 matches, merged chunk file created by `run_book.py`, `config/domains_v2.json`, `config/api.yaml`
- Outputs:
  - `<output_root>/stage3/l0_principles.jsonl`
  - `<output_root>/stage3/progress.json`
  - `<output_root>/stage3/failed.json`
  - `<output_root>/stage3/quality_issues.json`
  - `<output_root>/stage3/cost_report.json`
- Gate: new principles appended in the current run

### Stage 3B
- Inputs: Stage 3 JSONL, Stage 2 matches, `config/api.yaml`
- Outputs:
  - `<output_root>/stage3/l0_principles_v2.jsonl`
  - `<output_root>/stage3/stage3b_report.txt`
- Gate: output JSONL contains at least one record

## Primary CLI
```bash
python3 scripts/run_book.py \
  --book-id mc_vol2 \
  --output-root /Users/jeff/culinary-engine/output \
  --questions /Users/jeff/culinary-engine/data/l0_question_master.json \
  --config config/api.yaml \
  --books config/books.yaml \
  --toc config/mc_toc.json \
  --domains config/domains_v2.json
```

## Partial Runs

Run Stage 2 through Stage 3B only:
```bash
python3 scripts/run_book.py \
  --book-id mc_vol2 \
  --output-root /Users/jeff/culinary-engine/output \
  --questions /Users/jeff/culinary-engine/data/l0_question_master.json \
  --config config/api.yaml \
  --books config/books.yaml \
  --toc config/mc_toc.json \
  --domains config/domains_v2.json \
  --start-stage 2
```

Stop after Stage 3:
```bash
python3 scripts/run_book.py \
  --book-id mc_vol2 \
  --output-root /Users/jeff/culinary-engine/output \
  --questions /Users/jeff/culinary-engine/data/l0_question_master.json \
  --config config/api.yaml \
  --books config/books.yaml \
  --toc config/mc_toc.json \
  --domains config/domains_v2.json \
  --stop-stage 3
```

Skip Stage 1 and reuse existing chunks:
```bash
python3 scripts/run_book.py \
  --book-id mc_vol2 \
  --output-root /Users/jeff/culinary-engine/output \
  --questions /Users/jeff/culinary-engine/data/l0_question_master.json \
  --config config/api.yaml \
  --books config/books.yaml \
  --toc config/mc_toc.json \
  --domains config/domains_v2.json \
  --skip-stage1
```

Plan a run without executing subprocesses:
```bash
python3 scripts/run_book.py \
  --book-id mc_vol2 \
  --output-root /tmp/test-output \
  --questions /dev/null \
  --config config/api.yaml \
  --books config/books.yaml \
  --toc config/mc_toc.json \
  --domains config/domains_v2.json \
  --dry-run
```

## Standalone Stage CLIs
Stage 1:
```bash
python3 scripts/stage1_pipeline.py \
  --book-id mc_vol2 \
  --output-dir /Users/jeff/culinary-engine/output/mc_vol2/stage1 \
  --config config/api.yaml \
  --books config/books.yaml \
  --toc config/mc_toc.json
```

Stage 2:
```bash
python3 scripts/stage2_match.py \
  --chunks /Users/jeff/culinary-engine/output/mc_vol2/stage1/chunks_smart.json \
           /Users/jeff/culinary-engine/output/mc_vol3/stage1/chunks_smart.json \
  --questions /Users/jeff/culinary-engine/data/l0_question_master.json \
  --output /Users/jeff/culinary-engine/output/stage2/question_chunk_matches.json \
  --config config/api.yaml
```

Stage 3:
```bash
python3 scripts/stage3_distill.py \
  --matches /Users/jeff/culinary-engine/output/stage2/question_chunk_matches.json \
  --chunks /Users/jeff/culinary-engine/output/stage3/merged_chunks.json \
  --output-dir /Users/jeff/culinary-engine/output/stage3 \
  --config config/api.yaml \
  --domains config/domains_v2.json \
  --append
```

Stage 3B:
```bash
python3 scripts/stage3b_causal.py \
  --input /Users/jeff/culinary-engine/output/stage3/l0_principles.jsonl \
  --matches /Users/jeff/culinary-engine/output/stage2/question_chunk_matches.json \
  --output /Users/jeff/culinary-engine/output/stage3/l0_principles_v2.jsonl \
  --report /Users/jeff/culinary-engine/output/stage3/stage3b_report.txt \
  --config config/api.yaml
```

## Quality Gates
- Stage 1: `chunks_smart.json` must exist and contain at least one chunk.
- Stage 2: `question_chunk_matches.json` must contain rows. `match_rate <= 0.8` is a warning, not a hard failure.
- Stage 3: `l0_principles.jsonl` must gain new records during the run.
- Stage 3B: `l0_principles_v2.jsonl` must contain records.
- Every run saves `run_report.json` even on failure, so you can see the last successful stage and the blocking error.

## Environment Variables
- `MINERU_API_KEY`
- `DASHSCOPE_API_KEY`
- `GEMINI_API_KEY`
- `L0_API_ENDPOINT`
- `L0_API_KEY`

## Dependencies
- Python 3.10+
- `requests`
- `PyYAML`
- Stage 1 support services referenced in `config/api.yaml`
- Any local models or APIs expected by the individual stage scripts

## Troubleshooting
- If `run_book.py` fails before Stage 1 or Stage 2 execution, check whether `scripts/stage1_pipeline.py` or `scripts/stage2_match.py` exists in the current checkout.
- If `--skip-stage1` fails, the runner could not find a valid `chunks_smart.json` for the requested `book_id`.
- If Stage 3 fails with missing chunk references, inspect `<output_root>/stage3/merged_chunks.json` and confirm the discovered Stage 1 outputs include the required book.
- If Stage 2 match rate is low, review the question file, the discovered chunk set, and the embedding configuration in `config/api.yaml`.
- If Stage 3B produces no rows, verify that `l0_principles.jsonl` contains records and that Stage 2 matches are readable.
