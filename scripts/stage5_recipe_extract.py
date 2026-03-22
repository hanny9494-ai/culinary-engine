#!/usr/bin/env python3
"""
Stage5 Step A: Recipe Structure Extraction
Uses local qwen3.5 (Ollama) to extract structured recipe JSON from chunk text.
"""
import json
import sys
import time
from pathlib import Path

try:
    from pydantic import BaseModel
    from typing import List, Optional
except ImportError:
    print("Installing pydantic...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "pydantic", "--break-system-packages"])
    from pydantic import BaseModel
    from typing import List, Optional

import requests


class Ingredient(BaseModel):
    item: str
    qty: Optional[float] = None
    unit: Optional[str] = None
    note: Optional[str] = None


class Step(BaseModel):
    order: int
    text: str
    action: str
    duration_min: Optional[int] = None
    temp_c: Optional[int] = None


class SubRecipeRef(BaseModel):
    ref_name: str
    ref_type: str
    ref_page: Optional[int] = None


class Recipe(BaseModel):
    recipe_type: str
    name: str
    yield_text: Optional[str] = None
    ingredients: List[Ingredient] = []
    steps: List[Step] = []
    equipment: List[str] = []
    sub_recipe_refs: List[SubRecipeRef] = []
    notes: Optional[str] = None


class ExtractionResult(BaseModel):
    recipes: List[Recipe] = []


SYSTEM_PROMPT = """你是专业烹饪配方结构化提取专家。从文本中提取所有食谱和子配方。

严格按JSON格式输出。如果文本中没有食谱，返回 {"recipes": []}

### 提取规则

1. 食材提取：
   - item: 食材名称（保留原文语言）
   - qty: 数字（"to taste"或无量 → null）
   - unit: 单位（g/mL/oz/lb/tsp/tbsp/cup/个/只/条，无单位 → null）
   - note: 额外说明（如"drained", "room temperature", "38% milkfat"）

2. 步骤提取：
   - order: 序号
   - text: 完整步骤文字（保留原文）
   - action: 核心动作词（mix/bake/ferment/fold/chill/fry/boil/steam等）
   - duration_min: 时间（分钟，没有明确时间 → null）
   - temp_c: 温度摄氏度（华氏自动转换，没有 → null）

3. 子配方引用（关键）：
   识别以下三种引用模式：

   模式A — 页码引用：
     "Classic Puff Pastry (p. 318)" 或 "see page 535"
     → ref_type: "page_ref", ref_name: "Classic Puff Pastry", ref_page: 318

   模式B — 同文内联定义：
     同一段文本中定义了多个组件（如独立的CARDAMOM OIL段）
     → 每个组件提取为独立的子配方
     → 主配方的 sub_recipe_refs 引用组件名
     → ref_type: "inline_def"

   模式C — 名称引用（无页码）：
     "use the chicken stock" 或 "the ramen broth"
     → ref_type: "name_ref", ref_name: "chicken stock", ref_page: null

4. 主配方 vs 子配方判断：
   - 有"TO PLATE"/"TO FINISH"/"ASSEMBLY"段 → 这是主配方
   - 有独立食材表但被主配方引用 → 这是子配方
   - 有"Basic Recipe"/"Foundation"标记 → 这是子配方

### 输出JSON格式

{
  "recipes": [
    {
      "recipe_type": "main" 或 "sub_recipe",
      "name": "食谱名称",
      "yield_text": "产量（原文）",
      "ingredients": [
        {"item": "bread flour", "qty": 1000, "unit": "g", "note": null}
      ],
      "steps": [
        {"order": 1, "text": "完整步骤文字", "action": "mix", "duration_min": 20, "temp_c": null}
      ],
      "equipment": ["stand mixer", "sheet pan"],
      "sub_recipe_refs": [
        {"ref_name": "Classic Puff Pastry", "ref_type": "page_ref", "ref_page": 318}
      ],
      "notes": null
    }
  ]
}

### 关键约束
- 华氏温度必须转为摄氏度（F→C），保留整数
- 一段文本可能包含多个食谱（主+子），全部提取
- 子配方如果在同一文本中有完整定义，同时提取为独立 recipe_type: "sub_recipe"
- 纯叙事没有可提取配方结构 → 返回 {"recipes": []}
- 不要编造文本中没有的信息
- 只输出JSON，不要输出任何其他文字"""


def call_ollama(text, model="qwen3.5:latest"):
    resp = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"提取以下文本中的食谱：\n\n{text}"},
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 4096, "think": False},
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def parse_response(raw_text):
    text = raw_text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None, "No JSON found in response"

    json_str = text[start:end]

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc}"

    try:
        result = ExtractionResult(**data)
        return result, None
    except Exception as exc:
        return None, f"Pydantic validation error: {exc}"


def extract_recipe(text, model="qwen3.5:latest"):
    for attempt in range(3):
        try:
            start = time.time()
            raw = call_ollama(text, model)
            elapsed = time.time() - start

            result, error = parse_response(raw)

            if result is not None:
                return result, elapsed, None

            if attempt < 2:
                print(f"    Attempt {attempt + 1} failed: {error}, retrying...")
                continue
            return None, elapsed, error
        except Exception as exc:
            if attempt < 2:
                print(f"    Attempt {attempt + 1} exception: {exc}, retrying...")
                continue
            return None, 0, str(exc)


TEST_CASES = {
    "test1_professional_baking": {
        "description": "Structured format: ingredient table + numbered steps + page refs",
        "expected": "1 main (Praline Millefeuille) + 1 sub (Praline Pailletine) + page_refs to p.318, p.535",
        "text": """PRALINE MILLEFEUILLE
Yield: one pastry, about 6 × 10 in. (15 × 25 cm) and weighing about 2½ lb (1200 g)
Ingredients U.S. Metric
Classic Puff Pastry (p. 318) 1 lb 4 oz 630 g
Confectioners' sugar as needed as needed
Praline Cream (p. 535) 1 lb 500 g
Praline Pailletine (recipe below) 5 oz 150 g
Garnish
Caramelized nuts as desired as desired
PROCEDURE
1. Roll out the puff pastry to a rectangle about 13 × 20 in. (33 × 52 cm). Place on a sheet pan lined with parchment paper. Dock the dough and refrigerate for 20 minutes.
2. Bake at 400°F (200°C). When the pastry is about four-fifths baked, remove from the oven and dredge generously with confectioners' sugar.
3. Raise the oven heat to 475°F (240°C). Return the pastry to the oven and bake until the sugar caramelizes, 2–3 minutes.
4. Remove from the oven and let cool.
5. With a serrated knife, trim the edges of the pastry so they are straight and square. Then cut crosswise into 3 equal rectangles.
6. Spread one of the pastry rectangles with a layer of praline cream 5/8 in. (1.5 cm) thick. Cover with a second layer of pastry.
7. Top with the praline pailletine and then another layer of the praline cream.
8. Cover with the third layer of pastry.
9. Decorate the top as desired with caramelized nuts.

PRALINE PAILLETINE
Ingredients U.S. Metric
Milk chocolate couverture 1 oz 25 g
Cocoa butter 0.25 oz 6 g
Almond-hazelnut praline paste 4 oz 100 g
Ice cream wafers (pailletine), crushed 1 oz 25 g
Total weight: 6 oz 156 g
PROCEDURE
1. Melt the chocolate and cocoa butter in a bowl over a hot-water bath.
2. Mix in the praline paste.
3. Add the crushed wafers and mix in.
4. To use in Praline Millefeuille (above), spread on a sheet pan to a thickness of about 1/4 in. (5 mm), making a rectangle about 6 × 10 in. (15 × 25 cm).
5. Place in the refrigerator to harden.""",
    },
    "test2_noma": {
        "description": "Multi-component format: 4 sub-recipes + TO PLATE assembly",
        "expected": "1 main (Cardamom-Scented Candle / TO PLATE) + 4 subs (Candle, Oil, Wick, Perfume), all inline_def",
        "text": """CARDAMOM-SAFFRON CANDLE
100 g sugar
175 g glucose syrup
375 mL cream (38% milkfat)
35 g cardamom pods
0.3 g saffron
90 g butter
9 g salt
7 mL white wine vinegar
0.7% agar
Liquid nitrogen
Lightly toast the cardamom pods and the saffron in a pan. Once toasted, break them apart with a mortar and pestle and toss them in with the cream. Bring to the fermentation lab to sonicate the mixture together at 30% amplitude for 5 minutes while stirring frequently over ice. Once sonicated, strain the cream with a fine-mesh nylon sieve and discard the pods and the saffron.
From there, place the sugar, salt, glucose, and 300 mL of the infused cream in a pot. Cook the mixture until it reaches 108°C on a candy thermometer. While it's cooking, melt the butter in another pot on the side. Once the caramel is up to temperature, add the melted butter and vinegar. Return the mixture to the heat and cook it again until it reaches 114°C. Once up to temperature, remove it from the heat, and wait until the mixture cools down to 70°C. Weigh the mixture to calculate the amount of agar necessary, then mix in the agar and the remaining 75 g cream. Heat the mixture once more to activate the agar.
When shaping the candles, keep the caramel mix warm on the stove for ease of processing. In a Styrofoam ice cream container fill up 4 cm diameter silicone molds with liquid nitrogen and wait until they are frozen. Once frozen, pour the nitro out of the molds and into the Styrofoam container so that the molds are now surrounded by the nitro. Fill up the mold with the warm caramel and wait 10 to 15 seconds. Once the caramel begins to be set, remove the mold from the Styrofoam, flip it upside down, and rest it on a skinny yogurt cup so that the caramel starts to drip down from the mold into the yogurt cup. Move this dripping caramel immediately to the blast freezer to set. Once it is completely set, remove the candle from the mold and make a small hole for the wick in the center of the candle with a metal skewer. Keep the candle in a 1 L container in the blast freezer.

CARDAMOM OIL
300 g grapeseed oil
100 g cardamom pods
Combine the cardamom pods and the oil in a pot. Over low heat, infuse the cardamom and oil for 30 minutes. Once infused, remove from the stove, and lightly blend it with an immersion blender. Once blended, cover the pot with foil and rest for 1 hour. Once rested, strain the oil through a fine-mesh nylon sieve. Reserve the oil in the fridge and discard the cardamom.

WALNUT WICK
Walnuts
Find the biggest dried walnuts you can possibly find. Set a combi oven to 90°C dry heat, with 70% humidity (30% fan). Lay the walnuts in one flat layer in the oven for a few minutes. Once warmed, retrieve the walnuts, and shave the skin off using a very sharp knife. Split the shaved walnuts in half and trim the edges. From each half of the walnut, you should be able to get 2 wicks cut approximately into the shape and size of matchsticks—approximately 3 mm thick. Reserve the walnut wicks in an airtight container until service.

CARDAMOM PERFUME
200 mL filtered water
35 g cardamom pods
Combine the cardamom and the water in a container. Using an immersion blender, blend till the cardamom is broken apart and infused into the water. Strain the mixture through a fine-mesh nylon sieve and reserve in a spray bottle.

TO PLATE
Cardamom Oil
Cardamom-Saffron Candle
Walnut Wick
Cardamom Perfume
Keep the candles in the blast freezer at -30°C. Brush the plates with a bit of cardamom oil (to prevent the candle from sticking to the plate) and keep them in the blast freezer. When called out, put the candle on the cold plate, spray it once with cardamom perfume, and place the wick in the candle. Double-check that the candle is not too frozen. Light the wick just before leaving the kitchen to walk to the table.""",
    },
    "test3_narrative": {
        "description": "Narrative format: story mixed with recipe, implicit references",
        "expected": "Possibly empty or partial extraction. name_ref to 'ramen broth' if detected",
        "text": """bo ssäm SERVES 6 TO 8
Our bo ssäm was a long time in the making before it showed up on the menu. I'd had an inkling for years it would be a good idea—bo ssäm is a supercommon dish in Korean restaurants, though the ingredients and cooking that go into it are frequently an afterthought. The oysters are usually Gulf oysters from a bucket, the kind that are really only suited to frying; the pork is belly that's been boiled into submission. Almost every time I ate it at a restaurant, I'd think about how much better it would be if all the ingredients were awesome.
The first time we made one was for family meal back when we'd just started serving kimchi puree on our oysters at Noodle Bar. One of the new cooks was fucking up oysters left and right, so I made him shuck a few dozen perfectly, and then we ate them ssäm-style: wrapped up in lettuce with rice, kimchi, and some shredded pork shoulder that was otherwise destined for the ramen bowl. (The shoulder in our bo ssäm is, essentially, the same shoulder we put in the soup at Noodle Bar.)""",
    },
}


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3.5:latest"
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output/stage5_pilot")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Model: {model}")
    print(f"Output: {output_dir}")
    print(f"Test cases: {len(TEST_CASES)}")
    print()

    results = {}

    for test_id, test in TEST_CASES.items():
        print(f"=== {test_id} ===")
        print(f"  Description: {test['description']}")
        print(f"  Expected: {test['expected']}")
        print(f"  Text length: {len(test['text'])} chars")
        print("  Extracting...", end=" ", flush=True)

        result, elapsed, error = extract_recipe(test["text"], model)

        if error:
            print(f"FAILED ({elapsed:.1f}s): {error}")
            results[test_id] = {"status": "failed", "error": error, "elapsed": elapsed}
        else:
            n_recipes = len(result.recipes)
            print(f"OK ({elapsed:.1f}s)")
            print(f"  Recipes found: {n_recipes}")
            for recipe in result.recipes:
                print(f"    [{recipe.recipe_type}] {recipe.name}")
                print(
                    f"      ingredients: {len(recipe.ingredients)}, steps: {len(recipe.steps)}, equipment: {len(recipe.equipment)}"
                )
                if recipe.sub_recipe_refs:
                    refs = [f"{ref.ref_name}({ref.ref_type})" for ref in recipe.sub_recipe_refs]
                    print(f"      refs: {refs}")

            results[test_id] = {
                "status": "ok",
                "elapsed": elapsed,
                "n_recipes": n_recipes,
                "recipes": [recipe.model_dump() for recipe in result.recipes],
                "expected": test["expected"],
            }

        with open(output_dir / f"{test_id}.json", "w", encoding="utf-8") as handle:
            json.dump(results[test_id], handle, ensure_ascii=False, indent=2)

        print()

    with open(output_dir / "pilot_summary.json", "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for test_id, result in results.items():
        status = result["status"]
        elapsed = result.get("elapsed", 0)
        if status == "ok":
            print(f"  {test_id}: ✅ {result['n_recipes']} recipes ({elapsed:.1f}s)")
        else:
            print(f"  {test_id}: ❌ {result.get('error', 'unknown')} ({elapsed:.1f}s)")

    print()
    print("=== QUALITY CHECK ===")
    print()
    print("For Jeff to review:")
    print("  test1: Should have 1 main + 1 sub, page_refs to p.318/p.535")
    print("  test2: Should have 1 main + 4 subs, all inline_def")
    print("  test3: Should be empty or partial (narrative text)")
    print()
    print(f"Full results saved to: {output_dir}/")


if __name__ == "__main__":
    main()
