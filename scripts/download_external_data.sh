#!/bin/bash
# 下载全部外部数据源 — 在终端直接运行，不要在 Claude Code 里跑
# Usage: bash scripts/download_external_data.sh

set -e
cd ~/culinary-engine/data/external
CURL="curl --noproxy '*' -fS -L --max-time 300 --retry 2"
PYTHON_BIN="python3"
VENV_DIR=".venv_external_data"

ensure_python_module() {
  local module="$1"
  local package="${2:-$1}"
  if ! "$PYTHON_BIN" -c "import ${module}" >/dev/null 2>&1; then
    echo "缺少 Python 依赖: ${package}"
    echo "创建专用虚拟环境: ${VENV_DIR}"
    if [ ! -x "${VENV_DIR}/bin/python" ]; then
      python3 -m venv "${VENV_DIR}"
    fi
    PYTHON_BIN="${PWD}/${VENV_DIR}/bin/python"
    "${PYTHON_BIN}" -m pip install "${package}"
  fi
}

ensure_zip_like_file() {
  local path="$1"
  "$PYTHON_BIN" - "$path" <<'PY'
import sys
from zipfile import ZipFile, BadZipFile

path = sys.argv[1]
try:
    with ZipFile(path):
        pass
except BadZipFile as exc:
    raise SystemExit(f"下载文件不是有效的 Office/ZIP 文件: {path} ({exc})")
PY
}

fetch_optional() {
  local output="$1"
  shift
  local url
  for url in "$@"; do
    if $CURL -o "$output" "$url"; then
      return 0
    fi
  done
  rm -f "$output"
  return 1
}

post_download() {
  local output="$1"
  local url="$2"
  shift 2
  if ! curl --noproxy '*' -fS -L --max-time 300 --retry 2 \
    -A 'Mozilla/5.0' \
    -o "$output" \
    -X POST "$url" "$@"; then
    rm -f "$output"
    return 1
  fi
}

ensure_python_module openpyxl

echo "=== 1/14 uk_cofid ==="
$CURL -o uk_cofid/cofid-datafile.xlsx "https://assets.publishing.service.gov.uk/media/60538b91e90e07527df82ae4/McCance_Widdowsons_Composition_of_Foods_Integrated_Dataset_2021..xlsx"
ensure_zip_like_file "uk_cofid/cofid-datafile.xlsx"
"$PYTHON_BIN" -c "
import openpyxl, csv
wb = openpyxl.load_workbook('uk_cofid/cofid-datafile.xlsx')
for sheet in wb.sheetnames:
    ws = wb[sheet]
    with open(f'uk_cofid/{sheet.lower()}.csv', 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows(ws.iter_rows(values_only=True))
    print(f'  {sheet}: {ws.max_row} rows')
"
ls -lh uk_cofid/

echo "=== 2/14 japanese_mext ==="
$CURL -o japanese_mext/general_composition_2023.xlsx "https://www.mext.go.jp/content/20260327-mxt_kagsei-mext-000029402_02.xlsx"
ensure_zip_like_file "japanese_mext/general_composition_2023.xlsx"
"$PYTHON_BIN" -c "
import openpyxl, csv
wb = openpyxl.load_workbook('japanese_mext/general_composition_2023.xlsx', read_only=True)
ws = wb[wb.sheetnames[0]]
with open('japanese_mext/general_composition_main.csv', 'w', newline='', encoding='utf-8') as f:
    csv.writer(f).writerows(ws.iter_rows(values_only=True))
print(f'  {ws.max_row} rows')
wb.close()
"
ls -lh japanese_mext/

echo "=== 3/14 flavordb2 ==="
fetch_optional flavordb2/flavordb.csv \
  "https://raw.githubusercontent.com/wannasleepforlong/flavordb/master/flavordb.csv" || \
echo "  WARNING: flavordb main table download failed"
fetch_optional flavordb2/molecules.csv \
  "https://raw.githubusercontent.com/wannasleepforlong/flavordb/master/molecules.csv" || \
echo "  WARNING: flavordb molecules download failed"
ls -lh flavordb2/

echo "=== 4/14 aromadb ==="
fetch_optional aromadb/flavornet.tsv \
  "https://www.flavornet.org/flavornet.html" || \
echo "  WARNING: flavornet download failed"
fetch_optional aromadb/VCF_supplement_data.xlsx \
  "https://zenodo.org/records/16122491/files/VCF_supplement_data.xlsx" || \
echo "  WARNING: VCF supplement download failed"
ls -lh aromadb/

echo "=== 5/14 bitterdb ==="
fetch_optional bitterdb/BitDB.txt \
  "https://web.archive.org/web/20230602001039/https://bitterdb.agri.huji.ac.il/dwnld/BitDB.txt" || \
echo "  WARNING: bitterdb download failed"
ls -lh bitterdb/

echo "=== 6/14 supersweet ==="
fetch_optional supersweet/sweet_nonsweet_compounds.csv \
  "https://raw.githubusercontent.com/Istarkovs/sweet-nonsweet/main/sweet_nonsweet.csv" \
  "https://raw.githubusercontent.com/Istarkovs/sweet-nonsweet/master/sweet_nonsweet.csv" || \
echo "  WARNING: supersweet download failed"
ls -lh supersweet/

echo "=== 7/14 phenol_explorer ==="
# Try Wayback Machine for phenol-explorer data
$CURL -o phenol_explorer/foods.csv "https://web.archive.org/web/2023/https://phenol-explorer.eu/downloads/foods.csv" || echo "  WARNING: phenol_explorer download failed, try manually"
ls -lh phenol_explorer/ 2>/dev/null

echo "=== 8/14 chinese_recipes_kg ==="
# meishichina 原始仓库已失效，改用公开中文菜谱替代集
fetch_optional chinese_recipes_kg/chinese_recipe_small.csv \
  "https://huggingface.co/datasets/wh1223/Chinese_Recipe_small/resolve/main/cookery1.csv" || \
echo "  WARNING: chinese_recipes_kg needs manual download — public mirrors unavailable"
ls -lh chinese_recipes_kg/ 2>/dev/null

echo "=== 9/14 korean_food_db ==="
if [ -f "korean_food_db/StandardFoodCompositionTableEng.xlsx" ] && \
   ensure_zip_like_file "korean_food_db/StandardFoodCompositionTableEng.xlsx" >/dev/null 2>&1; then
  echo "  reuse existing StandardFoodCompositionTableEng.xlsx"
else
  success=0
  for attempt in 1 2 3; do
    echo "  attempt ${attempt}/3"
    cookie_jar="$(mktemp)"
    if curl --noproxy '*' --http1.1 -fS -L --max-time 90 --retry 0 \
      -A 'Mozilla/5.0' \
      -c "$cookie_jar" \
      -b "$cookie_jar" \
      -X POST "https://koreanfood.rda.go.kr/eng/fctCustTbl/downPop" \
      -o /dev/null \
      --data-urlencode "gubun=" \
      --data-urlencode "sort=" && \
      curl --noproxy '*' --http1.1 -fS -L --max-time 180 --retry 0 \
      -A 'Mozilla/5.0' \
      -c "$cookie_jar" \
      -b "$cookie_jar" \
      -X POST "https://koreanfood.rda.go.kr/eng/fctCustTbl/excelDownload" \
      -o "korean_food_db/StandardFoodCompositionTableEng.xlsx" \
      --data-urlencode "gubun=" \
      --data-urlencode "sort=" \
      --data-urlencode "usepurps=441039" \
      --data-urlencode "occpgrupp=441047" \
      --data-urlencode "userNation=441168" && \
      ensure_zip_like_file "korean_food_db/StandardFoodCompositionTableEng.xlsx" >/dev/null 2>&1; then
      success=1
      rm -f "$cookie_jar"
      break
    fi
    rm -f "$cookie_jar"
    rm -f "korean_food_db/StandardFoodCompositionTableEng.xlsx"
    sleep 3
  done
  if [ "$success" != "1" ]; then
    echo "  WARNING: korean_food_db download failed — koreanfood.rda.go.kr connection unstable"
  fi
fi
ls -lh korean_food_db/ 2>/dev/null

echo "=== 10/14 chinese_food_bench ==="
# ChineseFoodBench 原始公开源失效，改用公开中文食物 caption 数据集替代
if [ -f "chinese_food_bench/chinese_food_caption.tar.gz" ]; then
  echo "  reuse existing chinese_food_caption.tar.gz"
else
  if ! "$PYTHON_BIN" - <<'PY'
from pathlib import Path
from urllib.request import urlopen

url = "https://huggingface.co/datasets/ADVISORYz/chinese_food_caption/resolve/main/chinese_food_caption.tar.gz"
out = Path("chinese_food_bench/chinese_food_caption.tar.gz")
with urlopen(url, timeout=120) as response:
    out.write_bytes(response.read())
print(f"  saved {out.stat().st_size} bytes")
PY
  then
    echo "  WARNING: chinese_food_bench needs manual download — public mirrors unavailable"
  fi
fi
ls -lh chinese_food_bench/ 2>/dev/null

echo "=== 11/14 efsa_openfoodtox ==="
# EFSA OpenFoodTox 毒理学数据
fetch_optional efsa_openfoodtox/OpenFoodTOxTX22051.xlsx \
  "https://zenodo.org/records/344883/files/OpenFoodTOxTX22051.xlsx?download=1" || \
echo "  WARNING: efsa_openfoodtox full database download failed"
fetch_optional efsa_openfoodtox/SubstanceCharacterisation_KJ.xlsx \
  "https://zenodo.org/records/344883/files/SubstanceCharacterisation_KJ.xlsx?download=1" || \
echo "  WARNING: efsa_openfoodtox substance characterisation download failed"
ls -lh efsa_openfoodtox/ 2>/dev/null

echo "=== 12/14 foodllm_data ==="
# FoodieQA 已 gated，改用公开 NutritionQA 作为食品 QA 替代
fetch_optional foodllm_data/nutritionqa_test.parquet \
  "https://huggingface.co/datasets/yyupenn/NutritionQA/resolve/main/data/test-00000-of-00001.parquet" || \
echo "  WARNING: NutritionQA substitute download failed"
ls -lh foodllm_data/ 2>/dev/null

echo "=== 13/14 global_fungi ==="
# FungalTraits — 全球真菌数据（含食用菌子集）
fetch_optional global_fungi/funtothefun.csv \
  "https://raw.githubusercontent.com/traitecoevo/fungaltraits/master/funtothefun.csv" || \
echo "  WARNING: global_fungi needs manual download — search 'FungalTraits dataset'"
ls -lh global_fungi/ 2>/dev/null

echo "=== 14/14 mesh_food_terms ==="
# MeSH 食品术语（从 NLM 下载 MeSH descriptor XML，提取食品分支）
$CURL -o mesh_food_terms/desc2026.gz "https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.gz" || \
echo "  WARNING: mesh_food_terms needs manual download — https://www.nlm.nih.gov/databases/download/mesh.html"
ls -lh mesh_food_terms/ 2>/dev/null

echo ""
echo "=== 下载完成，验证全部 14 个数据源 ==="
for d in uk_cofid japanese_mext flavordb2 aromadb bitterdb supersweet phenol_explorer chinese_recipes_kg korean_food_db chinese_food_bench efsa_openfoodtox foodllm_data global_fungi mesh_food_terms; do
  count=$(find "$d" -type f -not -name "*.md" -not -name "manifest.json" -not -name ".DS_Store" 2>/dev/null | wc -l | tr -d ' ')
  size=$(du -sh "$d" 2>/dev/null | cut -f1)
  if [ "$count" = "0" ]; then
    echo "  ❌ $d — 空"
  else
    echo "  ✅ $d — ${count}文件, ${size}"
  fi
done
echo ""
echo "注意：USDA (usda_fdc) 已决定不使用 — packaged food 污染风险"
