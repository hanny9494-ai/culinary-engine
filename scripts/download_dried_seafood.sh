#!/bin/bash
# 按 URL 列表下载干鮑魚海味寶典全部页面图片。
set -euo pipefail

DIR="${DIR:-$HOME/culinary-engine/data/external/dried_seafood_encyclopedia}"
IMAGES_DIR="${IMAGES_DIR:-$DIR/images}"
LIST_FILE="${LIST_FILE:-/tmp/fliphtml_all_pages.json}"
MIN_IMAGE_BYTES="${MIN_IMAGE_BYTES:-50000}"
USER_AGENT="${USER_AGENT:-Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36}"
REFERER="${REFERER:-https://online.fliphtml5.com/gdetf/weyx/}"
ORIGIN="${ORIGIN:-https://online.fliphtml5.com}"

mkdir -p "$IMAGES_DIR"

if [[ ! -f "$LIST_FILE" ]]; then
  echo "缺少 URL 列表文件: $LIST_FILE" >&2
  echo "请先把 fliphtml_all_pages.json 放到该路径，或用 LIST_FILE=/path/to/file.json 指定。" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

python3 - "$LIST_FILE" "$TMP_DIR/urls.tsv" <<'PY'
import json
import sys
from pathlib import Path

list_file = Path(sys.argv[1])
out_file = Path(sys.argv[2])

pages = json.loads(list_file.read_text())
if not isinstance(pages, list) or not pages:
    raise SystemExit(f"URL 列表为空或格式不正确: {list_file}")

seen = set()
with out_file.open("w", encoding="utf-8") as fh:
    for item in pages:
        if not isinstance(item, dict):
            raise SystemExit("列表项不是对象")
        page = item.get("page")
        url = item.get("url")
        if not isinstance(page, int) or page <= 0:
            raise SystemExit(f"非法页码: {item!r}")
        if not isinstance(url, str) or not url.startswith("http"):
            raise SystemExit(f"非法 URL: {item!r}")
        if page in seen:
            raise SystemExit(f"重复页码: {page}")
        seen.add(page)
        fh.write(f"{page}\t{url}\n")
PY

TOTAL_PAGES="$(wc -l < "$TMP_DIR/urls.tsv" | tr -d ' ')"
echo "=== 下载 ${TOTAL_PAGES} 页图片 ==="
echo "URL 列表: $LIST_FILE"
echo "保存目录: $IMAGES_DIR"

download_one() {
  local page="$1"
  local url="$2"
  local output="${IMAGES_DIR}/page_$(printf '%03d' "$page").webp"
  local headers="${TMP_DIR}/headers_${page}.txt"

  curl \
    --noproxy '*' \
    -f \
    -sS \
    -L \
    --retry 3 \
    --retry-delay 1 \
    --connect-timeout 20 \
    -A "$USER_AGENT" \
    -H "Referer: $REFERER" \
    -H "Origin: $ORIGIN" \
    -H 'Accept: image/avif,image/webp,image/apng,image/*,*/*;q=0.8' \
    -D "$headers" \
    -o "$output" \
    "$url"

  if file -b --mime-type "$output" | grep -q '^text/html$'; then
    echo "下载到 HTML 错误页: page ${page}" >&2
    sed -n '1,20p' "$headers" >&2 || true
    return 1
  fi

  local size
  size="$(wc -c < "$output" | tr -d ' ')"
  if (( size < MIN_IMAGE_BYTES )); then
    echo "文件过小: ${output} (${size} bytes < ${MIN_IMAGE_BYTES})" >&2
    return 1
  fi
}

while IFS=$'\t' read -r page url; do
  download_one "$page" "$url"
  if (( page % 25 == 0 )) || (( page == TOTAL_PAGES )); then
    echo "  ${page}/${TOTAL_PAGES}"
  fi
done < "$TMP_DIR/urls.tsv"

echo ""
echo "=== 验证 ==="
FILE_COUNT="$(find "$IMAGES_DIR" -maxdepth 1 -name 'page_*.webp' | wc -l | tr -d ' ')"
echo "Files: ${FILE_COUNT}"
echo "Total: $(du -sh "$IMAGES_DIR" | cut -f1)"
echo "Samples:"
for sample in 1 50 100 200 246; do
  file_path="${IMAGES_DIR}/page_$(printf '%03d' "$sample").webp"
  if [[ -f "$file_path" ]]; then
    echo "  $(basename "$file_path"): $(wc -c < "$file_path") bytes"
  fi
done
