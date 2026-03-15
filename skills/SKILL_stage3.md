# Stage 3 Distillation Skill

## Purpose
Use this workflow for the Stage 3 knowledge distillation stack:

`Stage 2 matches -> Stage 3 distill -> Stage 3B causal enrichment -> low-hit scan`

## Entry Points
Run Stage 3:

```bash
python3 scripts/stage3_distill.py \
  --matches output/stage2/question_chunk_matches.json \
  --chunks output/stage1/chunks_smart.json \
  --output-dir output/stage3 \
  --config config/api.yaml \
  --domains config/domains_v2.json
```

Run Stage 3B:

```bash
python3 scripts/stage3b_causal.py \
  --input output/stage3/l0_principles.jsonl \
  --matches output/stage2/question_chunk_matches.json \
  --output output/stage3/l0_principles_v2.jsonl \
  --report output/stage3/stage3b_report.txt \
  --config config/api.yaml
```

Run low-hit scan:

```bash
python3 scripts/scan_low_hit.py \
  --mc-chunks "output/mc/vol*/stage1/chunks_smart.json" \
  --matches output/stage2/question_chunk_matches.json \
  --output output/gap_analysis/candidate_questions.json \
  --config config/api.yaml \
  --domains config/domains_v2.json
```

## Output Contract
- `output/stage3/l0_principles.jsonl`
- `output/stage3/progress.json`
- `output/stage3/failed.json`
- `output/stage3/quality_issues.json`
- `output/stage3/cost_report.json`
- `output/stage3/l0_principles_v2.jsonl`
- `output/stage3/stage3b_report.txt`
- `output/gap_analysis/candidate_questions.json`

## Operational Notes
- All Claude settings come from `config/api.yaml` through `scripts/utils/claude_client.py`
- Domain IDs are always loaded from `config/domains_v2.json`
- `stage3_distill.py` supports OFC `{"chunks": [...]}` and MC `[...]` chunk files
- `--append` keeps existing `l0_principles.jsonl` and continues numbering from prior output
- `progress.json` stores completed question IDs for resume
- `failed.json` records questions that exhausted retries
- Stage 3 quality checks flag long quotes, missing numeric claims, and missing core principle fields
- Stage 3B resumes by skipping source `principle_id`s already present in the output JSONL
- The low-hit scan is intended for MC blind spots and should be reviewed manually before adding new questions

## Recommended Run Order
1. `python3 scripts/stage3_distill.py ... --dry-run --preview 3`
2. `python3 scripts/stage3_distill.py ... --limit 5`
3. `python3 scripts/stage3_distill.py ...`
4. `python3 scripts/stage3b_causal.py ...`
5. `python3 scripts/scan_low_hit.py ... --threshold 0.55 --max-chunks 200`

## Troubleshooting
- If Claude calls fail immediately, inspect `config/api.yaml` env expansion and the proxy endpoint
- If Stage 3 skips too much work, review `progress.json`, `failed.json`, and whether `--append` is intended
- If Stage 3B does not split obvious compound statements, inspect the source `scientific_statement` and rerun that record after removing its output line
- If low-hit output is noisy, lower `--max-chunks` first and inspect the dry-run preview before calling the API
