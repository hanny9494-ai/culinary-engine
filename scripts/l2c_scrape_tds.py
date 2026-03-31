#!/usr/bin/env python3
"""L2c TDS scraper — Boiron/Valrhona/Callebaut/CacaoBarry/Debic

Usage:
  python3 scripts/l2c_scrape_tds.py --brand boiron
  python3 scripts/l2c_scrape_tds.py --brand valrhona --dry-run
  python3 scripts/l2c_scrape_tds.py  # all brands
"""

# 清除代理（必须在 import requests 之前）
import os
for _k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
    os.environ.pop(_k, None)

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output" / "l2c" / "tds"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
DELAY = 2


def get_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.headers.update({"User-Agent": USER_AGENT,
                       "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                       "Accept-Language": "en-US,en;q=0.5"})
    return s


def _is_js_rendered(soup: BeautifulSoup) -> bool:
    body = soup.find("body")
    if body is None:
        return True
    return len(body.get_text(separator=" ", strip=True)) < 200


def _safe_text(tag) -> str:
    return tag.get_text(separator=" ", strip=True) if tag else ""


def _extract_tech_data(soup: BeautifulSoup) -> dict:
    """Generic: extract key-value pairs from tables and dl lists."""
    data = {}
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                data[_safe_text(cells[0]).lower().replace(" ", "_")] = _safe_text(cells[1])
    for dl in soup.find_all("dl"):
        for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
            data[_safe_text(dt).lower().replace(" ", "_")] = _safe_text(dd)
    return data


def _map_fields(tech_data: dict, field_map: dict) -> dict:
    result = {}
    for out_key, candidates in field_map.items():
        for c in candidates:
            if c in tech_data:
                result[out_key] = tech_data[c]
                break
    return result


# ---------------------------------------------------------------------------
# Boiron
# ---------------------------------------------------------------------------
BOIRON_BASE = "https://www.my-vb.com"
BOIRON_LIST = "https://www.my-vb.com/en/our-products"

BOIRON_FIELDS = {
    "brix": ["brix", "°brix"], "total_sugar_pct": ["total_sugar", "sugars", "total_sugars"],
    "acidity_g_per_100g": ["acidity", "total_acidity"], "ph": ["ph"],
    "fruit_content_pct": ["fruit_content", "fruit_percentage", "%_fruit"],
    "dry_matter_pct": ["dry_matter", "total_dry_matter"],
    "energy_kcal": ["energy", "energy_kcal"], "fat_g": ["fat", "total_fat"],
    "carbohydrate_g": ["carbohydrate", "carbohydrates"], "protein_g": ["protein", "proteins"],
}


def scrape_boiron(session, dry_run=False):
    print("[boiron] Fetching product list...")
    products, errors = [], []
    resp = session.get(BOIRON_LIST, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")
    if _is_js_rendered(soup):
        print("  WARNING: JS-rendered — TODO: use playwright")
        return {"brand": "boiron", "scraped_at": str(date.today()), "source_url": BOIRON_LIST,
                "status": "TODO: JS-rendered", "products": [], "errors": []}
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r'/en/(product|our-products)/[\w-]+', href):
            full = href if href.startswith("http") else BOIRON_BASE + href
            if full not in links: links.append(full)
    print(f"  Found {len(links)} products")
    for i, url in enumerate(links[:1 if dry_run else len(links)]):
        time.sleep(DELAY)
        try:
            r = session.get(url, timeout=30)
            s = BeautifulSoup(r.text, "html.parser")
            td = _extract_tech_data(s)
            name_tag = s.select_one("h1") or s.select_one(".product-title")
            pdf = next((a["href"] for a in s.find_all("a", href=True)
                        if a["href"].lower().endswith(".pdf") and any(k in a["href"].lower() for k in ["tds","tech","fiche"])), None)
            products.append({"product_name": _safe_text(name_tag), "product_url": url,
                             "specs": _map_fields(td, BOIRON_FIELDS), "raw_tech": td,
                             "tds_pdf_url": (pdf if pdf and pdf.startswith("http") else (BOIRON_BASE + pdf) if pdf else None)})
            print(f"  Boiron: {i+1}/{len(links)} — {_safe_text(name_tag)}")
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
    return {"brand": "boiron", "scraped_at": str(date.today()), "source_url": BOIRON_LIST, "products": products, "errors": errors}


# ---------------------------------------------------------------------------
# Valrhona
# ---------------------------------------------------------------------------
VALRHONA_BASE = "https://www.valrhona-professionals.com"
VALRHONA_LIST = "https://www.valrhona-professionals.com/en/our-range/chocolate"

VALRHONA_FIELDS = {
    "cocoa_pct": ["cocoa", "cocoa_%", "%_cocoa", "cacao"], "cocoa_butter_pct": ["cocoa_butter"],
    "total_fat_pct": ["total_fat", "fat"], "sugar_pct": ["sugar", "sugars"],
    "fluidity_rating": ["fluidity", "viscosity"], "flavor_notes": ["taste", "flavour", "flavor", "tasting_notes"],
}


def scrape_valrhona(session, dry_run=False):
    print("[valrhona] Fetching product list...")
    products, errors = [], []
    resp = session.get(VALRHONA_LIST, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")
    if _is_js_rendered(soup):
        print("  WARNING: JS-rendered — TODO: use playwright")
        return {"brand": "valrhona", "scraped_at": str(date.today()), "source_url": VALRHONA_LIST,
                "status": "TODO: JS-rendered", "products": [], "errors": []}
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r'/en/(our-range|product|chocolate)/[\w-]+', href):
            full = href if href.startswith("http") else VALRHONA_BASE + href
            if full not in links and full != VALRHONA_LIST: links.append(full)
    print(f"  Found {len(links)} products")
    for i, url in enumerate(links[:1 if dry_run else len(links)]):
        time.sleep(DELAY)
        try:
            r = session.get(url, timeout=30)
            s = BeautifulSoup(r.text, "html.parser")
            td = _extract_tech_data(s)
            name_tag = s.select_one("h1") or s.select_one(".product-name")
            products.append({"product_name": _safe_text(name_tag), "product_url": url,
                             "specs": _map_fields(td, VALRHONA_FIELDS), "raw_tech": td})
            print(f"  Valrhona: {i+1}/{len(links)} — {_safe_text(name_tag)}")
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
    return {"brand": "valrhona", "scraped_at": str(date.today()), "source_url": VALRHONA_LIST, "products": products, "errors": errors}


# ---------------------------------------------------------------------------
# Callebaut
# ---------------------------------------------------------------------------
CALLEBAUT_BASE = "https://www.callebaut.com"
CALLEBAUT_LIST = "https://www.callebaut.com/en-US/chocolate-video/products"

CALLEBAUT_FIELDS = {
    "cocoa_pct": ["cocoa", "cocoa_content", "%_cocoa"], "cocoa_butter_pct": ["cocoa_butter"],
    "total_fat_pct": ["total_fat", "fat"], "sugar_pct": ["sugar", "sugars"],
    "viscosity_pa": ["viscosity", "viscosity_(pa.s)", "fluidity"],
    "recipe_code": ["recipe", "product_code", "sku"],
}


def scrape_callebaut(session, dry_run=False):
    print("[callebaut] Fetching product list...")
    products, errors = [], []
    resp = session.get(CALLEBAUT_LIST, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")
    if _is_js_rendered(soup):
        print("  WARNING: JS-rendered — TODO: use playwright")
        return {"brand": "callebaut", "scraped_at": str(date.today()), "source_url": CALLEBAUT_LIST,
                "status": "TODO: JS-rendered", "products": [], "errors": []}
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r'/en-US/(chocolate|products|product)/[\w-]+', href):
            full = href if href.startswith("http") else CALLEBAUT_BASE + href
            if full not in links and full != CALLEBAUT_LIST: links.append(full)
    print(f"  Found {len(links)} products")
    for i, url in enumerate(links[:1 if dry_run else len(links)]):
        time.sleep(DELAY)
        try:
            r = session.get(url, timeout=30)
            s = BeautifulSoup(r.text, "html.parser")
            td = _extract_tech_data(s)
            name_tag = s.select_one("h1") or s.select_one(".product-detail__title")
            code_tag = s.select_one(".product-code") or s.select_one(".sku")
            p = {"product_name": _safe_text(name_tag), "product_url": url,
                 "specs": _map_fields(td, CALLEBAUT_FIELDS), "raw_tech": td}
            if code_tag: p["recipe_code"] = _safe_text(code_tag)
            products.append(p)
            print(f"  Callebaut: {i+1}/{len(links)} — {_safe_text(name_tag)}")
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
    return {"brand": "callebaut", "scraped_at": str(date.today()), "source_url": CALLEBAUT_LIST, "products": products, "errors": errors}


# ---------------------------------------------------------------------------
# Cacao Barry
# ---------------------------------------------------------------------------
CACAO_BARRY_BASE = "https://www.cacao-barry.com"
CACAO_BARRY_LIST = "https://www.cacao-barry.com/en-US/products"

CACAO_BARRY_FIELDS = {**CALLEBAUT_FIELDS, "origin": ["origin", "country_of_origin", "provenance"]}


def scrape_cacao_barry(session, dry_run=False):
    print("[cacao_barry] Fetching product list...")
    products, errors = [], []
    resp = session.get(CACAO_BARRY_LIST, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")
    if _is_js_rendered(soup):
        print("  WARNING: JS-rendered — TODO: use playwright")
        return {"brand": "cacao_barry", "scraped_at": str(date.today()), "source_url": CACAO_BARRY_LIST,
                "status": "TODO: JS-rendered", "products": [], "errors": []}
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r'/en-US/(products|product|chocolate)/[\w-]+', href):
            full = href if href.startswith("http") else CACAO_BARRY_BASE + href
            if full not in links and full != CACAO_BARRY_LIST: links.append(full)
    print(f"  Found {len(links)} products")
    for i, url in enumerate(links[:1 if dry_run else len(links)]):
        time.sleep(DELAY)
        try:
            r = session.get(url, timeout=30)
            s = BeautifulSoup(r.text, "html.parser")
            td = _extract_tech_data(s)
            name_tag = s.select_one("h1") or s.select_one(".product-detail__title")
            products.append({"product_name": _safe_text(name_tag), "product_url": url,
                             "specs": _map_fields(td, CACAO_BARRY_FIELDS), "raw_tech": td})
            print(f"  Cacao Barry: {i+1}/{len(links)} — {_safe_text(name_tag)}")
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
    return {"brand": "cacao_barry", "scraped_at": str(date.today()), "source_url": CACAO_BARRY_LIST, "products": products, "errors": errors}


# ---------------------------------------------------------------------------
# Debic
# ---------------------------------------------------------------------------
DEBIC_BASE = "https://www.debic.com"
DEBIC_LIST = "https://www.debic.com/en/products"

DEBIC_FIELDS = {
    "fat_pct": ["fat", "fat_content", "fat_%"], "protein_pct": ["protein", "proteins"],
    "carbohydrate_pct": ["carbohydrate", "carbohydrates"],
    "overrun_pct": ["overrun", "overrun_%"], "whipping_time": ["whipping_time", "whip_time"],
    "stability_hours": ["stability", "stability_(hours)"],
}


def scrape_debic(session, dry_run=False):
    print("[debic] Fetching product list...")
    products, errors = [], []
    resp = session.get(DEBIC_LIST, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")
    if _is_js_rendered(soup):
        print("  WARNING: JS-rendered — TODO: use playwright")
        return {"brand": "debic", "scraped_at": str(date.today()), "source_url": DEBIC_LIST,
                "status": "TODO: JS-rendered", "products": [], "errors": []}
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r'/en/(products|product)/[\w-]+', href):
            full = href if href.startswith("http") else DEBIC_BASE + href
            if full not in links and full != DEBIC_LIST: links.append(full)
    print(f"  Found {len(links)} products")
    for i, url in enumerate(links[:1 if dry_run else len(links)]):
        time.sleep(DELAY)
        try:
            r = session.get(url, timeout=30)
            s = BeautifulSoup(r.text, "html.parser")
            td = _extract_tech_data(s)
            name_tag = s.select_one("h1") or s.select_one(".product-title")
            products.append({"product_name": _safe_text(name_tag), "product_url": url,
                             "specs": _map_fields(td, DEBIC_FIELDS), "raw_tech": td})
            print(f"  Debic: {i+1}/{len(links)} — {_safe_text(name_tag)}")
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
    return {"brand": "debic", "scraped_at": str(date.today()), "source_url": DEBIC_LIST, "products": products, "errors": errors}


# ---------------------------------------------------------------------------
BRAND_SCRAPERS = {
    "boiron": scrape_boiron, "valrhona": scrape_valrhona,
    "callebaut": scrape_callebaut, "cacao_barry": scrape_cacao_barry, "debic": scrape_debic,
}


def main():
    parser = argparse.ArgumentParser(description="Scrape TDS from professional culinary brands.")
    parser.add_argument("--brand", choices=list(BRAND_SCRAPERS.keys()))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    session = get_session()
    brands = [args.brand] if args.brand else list(BRAND_SCRAPERS.keys())

    for brand in brands:
        print(f"\n=== {brand.upper()} ===")
        try:
            result = BRAND_SCRAPERS[brand](session, dry_run=args.dry_run)
        except Exception as e:
            result = {"brand": brand, "scraped_at": str(date.today()), "status": f"FATAL: {e}", "products": [], "errors": []}
        out = args.output_dir / f"{brand}_products.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"  Saved {len(result.get('products', []))} products to {out}")
        if brand != brands[-1]: time.sleep(DELAY)


if __name__ == "__main__":
    main()
