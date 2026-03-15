# Stage 1 Pipeline Skill

## Purpose
Use this workflow when running or debugging the Stage 1 ingestion pipeline:

`PDF/EPUB -> MinerU -> qwen-vl -> merge -> qwen3.5:2b split -> qwen3.5:9b annotate -> chunks_smart.json`

## Entry Point
Run:

```bash
python3 scripts/stage1_pipeline.py \
  --book-id mc_vol2 \
  --config config/api.yaml \
  --books config/books.yaml \
  --toc config/mc_toc.json \
  --output-dir /tmp/mc_vol2_stage1
```

## Step Map
- Step 0: Convert EPUB to PDF when the registered book type is `epub`
- Step 1: Submit the PDF to MinerU, auto-splitting when page or size limits are exceeded
- Step 2: Render PNG pages and call DashScope `qwen3-vl-plus`
- Step 3: Merge MinerU markdown with page-aware vision output
- Step 4: TOC-aware section splitting and chunk normalization
- Step 5: Annotate each chunk with a short Chinese summary and domain topics

## Important Flags
- `--start-step N --stop-step N`: run only a subset
- `--dry-run`: validate config, paths, and resume inference without calling external APIs
- `--repair-state`: rebuild `stage1_progress.json` from actual output files
- `--retry-annotations`: rerun only failed chunk annotations from `stage1/annotation_failures.json`
- `--watchdog 20`: fail fast when the active chunk output file stops growing for 20 minutes

## Output Contract
- `raw_mineru.md`
- `raw_vision.json`
- `raw_merged.md`
- `chunks_raw.json`
- `step4_quality.json`
- `stage1/chunks_smart.json`
- `stage1/annotation_failures.json`
- `stage1_progress.json`

## Quality Gates
- Step 4 must produce `total_chunks > 0`
- Step 4 must end with `lt50_chars == 0`
- Step 5 must satisfy `len(chunks_smart) == len(chunks_raw)`
- Step 5 must end with an empty `annotation_failures.json`

## Operational Notes
- API keys come from the environment via `config/api.yaml`
- Topic IDs are loaded from `config/domains_v2.json`
- Resume decisions are inferred from existing output files, not trusted from prior state alone
- For MC volumes, section boundaries come from `config/mc_toc.json`
