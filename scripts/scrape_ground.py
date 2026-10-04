#!/usr/bin/env python3
"""GroundDB scraper — pulls weapons/tools, creatures, consumables, trinkets, armor sets
from grounded.wiki.gg MediaWiki API with rate limiting and G2 filtering."""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

WIKI = "https://grounded.wiki.gg/api.php"
UA = "GroundDB/1.0 (site: grounded-db.pages.dev; contact franceiwhdbks865@gmail.com)"
OUT = Path(__file__).resolve().parent.parent / "src" / "data"
CACHE = Path(__file__).resolve().parent / "cache"
CACHE.mkdir(exist_ok=True)
DELAY = 0.7  # seconds between API calls


def api(params: dict, retries: int = 6) -> dict:
    params = {**params, "format": "json"}
    url = WIKI + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            print(f"  retry {attempt + 1} for {params.get('page', params.get('cmtitle', '?'))}: {e}")
            time.sleep(min(60, 5 * (2 ** attempt)))
    return {}


def category_members(cat: str) -> list[str]:
    titles, cont = [], {}
    while True:
        d = api({"action": "query", "list": "categorymembers", "cmtitle": f"Category:{cat}",
                 "cmlimit": "500", "cmnamespace": "0", **cont})
        if "query" not in d:
            break
        titles += [m["title"] for m in d["query"]["categorymembers"]]
        cont = d.get("continue")
        if not cont:
            break
        cont = {"cmcontinue": cont["cmcontinue"]}
        time.sleep(DELAY)
    return sorted(set(titles))


# --- wiki 魔术字展开 ---------------------------------------------------------
# 清洗器整段删无名模板，{{PAGENAME}}（条目名）随之消失，正文出现主语缺失残句。
_MAGIC_TITLE = re.compile(r"\{\{\s*(?:SUB|BASE|FULL)?PAGENAME(?:E)?\s*\}\}", re.I)
_MAGIC_GAME = re.compile(r"\{\{\s*(?:Gamename|Game|SITENAME|Sitename)\s*\}\}", re.I)
_MAGIC_DROP = re.compile(
    r"\{\{\s*(?:DISPLAYTITLE|DEFAULTSORT|#(?:expr|var|if|ifeq|ifexist|switch|tag|invoke|time|pos|len|replace|sub|explode|titleparts)[^}]*)\}\}",
    re.I,
)


def expand_magic(wt: str | None, title: str) -> str | None:
    """把 {{PAGENAME}} 换成条目名，丢弃解析器函数等元魔术字。"""
    if not wt:
        return wt
    wt = _MAGIC_TITLE.sub(lambda _m: title, wt)
    wt = _MAGIC_GAME.sub("Grounded", wt)
    wt = _MAGIC_DROP.sub("", wt)
    return wt


def get_wikitext(page: str) -> str | None:
    d = api({"action": "parse", "page": page, "prop": "wikitext"})
    if "parse" not in d:
        err = d.get("error", {}).get("info", "no parse in response")[:60]
        print(f"  MISS {page}: {err}")
        return None
    return expand_magic(d["parse"]["wikitext"]["*"], page)


def match_infobox(wikitext: str, family: str) -> tuple[str, str] | None:
    """Find {{Infobox/<name> ... }} where name starts with family. Returns (name, body).
    Uses brace-depth counting so nested templates (e.g. {{LootBox|...}}) don't truncate."""
    for m in re.finditer(r"\{\{(Infobox/[^|\n}]*)", wikitext):
        name = m.group(1)
        if not name.split("/")[1].lower().startswith(family.lower()) or "/G2" in name:
            continue
        depth, i, n = 1, m.end(), len(wikitext)
        while i < n - 1 and depth > 0:
            if wikitext[i : i + 2] == "{{":
                depth += 1
                i += 2
            elif wikitext[i : i + 2] == "}}":
                depth -= 1
                i += 2
            else:
                i += 1
        if depth != 0:
            continue
        return name, wikitext[m.end() : i - 2]
    return None


def parse_infobox_params(body: str) -> dict:
    """Parse |key = value lines (values may span lines until next |key=)."""
    params = {}
    for line in re.split(r"\n(?=\s*\|\s*[A-Za-z%0-9 _]+\s*=)", body):
        m = re.match(r"\s*\|\s*([A-Za-z%0-9 _]+?)\s*=\s*([\s\S]*)", line)
        if m:
            params[m.group(1).strip().lower()] = clean(m.group(2).strip())
    return params


def clean(v: str) -> str:
    v = re.sub(r"<[^>]+>", "", v)
    v = re.sub(r"\[\[([^|\]]*\|)?([^\]]*)\]\]", r"\2", v)
    v = re.sub(r"\{\{Icon\|([^|}]+)[^}]*\}\}", r"\1", v)
    v = re.sub(r"\{\{[^}]+\}\}", "", v)
    v = re.sub(r"'{2,}", "", v)
    v = re.sub(r"\s+", " ", v)
    return v.strip()


def slug(title: str) -> str:
    s = title.replace(" ", "_").replace("'", "").replace("!", "")
    for ch in ':*?"<>|':
        s = s.replace(ch, "")
    return s.strip(".").lstrip(".")


def first_sentence(wikitext: str) -> str:
    t = re.sub(r"\{\{[^}]+\}\}", "", wikitext)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\[\[([^|\]]*\|)?([^\]]*)\]\]", r"\2", t)
    t = re.sub(r"'{2,}", "", t)

    # 注意：旧写法 re.search(r"is a[^.]*\.", t) 会让匹配「从 is a 处开始」，
    # 于是句子主语（The Acorn Armor / ARC.R …）连同前置短语一起被丢掉，
    # 全站 408 条简介变成 "is a Tier 1 Heavy Armor Set in Grounded …"。
    # 正确做法：先定位含有 "is a/an" 的那一行，再取该行里这一句的完整句子。
    def _lead(line: str) -> str:
        m = re.search(r"\bis (?:a|an)\b", line)
        if not m:
            return ""
        # 从**行首**取到句末：句末 = 句点后跟「空格+大写」或行尾。
        # 不能用 rfind(". ") 找句首边界 —— 会把缩写里的点当成句末，
        # 例如 'The C.K.U. is a Tier 1 …' / 'The ARC.R is a …' 会把主语切掉。
        tail = line[m.end():]
        e = re.search(r"\.(?=\s+[A-Z]|\s*$)", tail)
        end = m.end() + (e.end() if e else len(tail))
        return line[:end].strip()

    for ln in t.splitlines():
        ln = ln.strip()
        # 跳过 infobox 参数行/模板行（`|image=…` 这类行里也可能出现 "is a"）
        if len(ln) < 20 or ln.startswith(("|", "=", "{", "}", "[", "!")):
            continue
        s = _lead(ln)
        if len(s) >= 20:
            return clean(s)[:240]
    parts = [p.strip() for p in t.split("\n")
             if len(p.strip()) > 40
             and not p.strip().startswith(("|", "=", "{", "}", "[", "!"))]
    return clean(parts[0][:220]) if parts else ""


HUB_PATTERNS = re.compile(r"\b(Unimplemented|Removed_Features|Draft|Armor_\(Grounded)\b")


def scrape_family(cat: str, family: str, game2_ok: bool = False) -> list[dict]:
    titles = category_members(cat)
    print(f"{cat}: {len(titles)} members")
    out = []
    for i, t in enumerate(titles):
        if t.startswith("Category:") or t.startswith("List of") or "(Grounded 2)" in t:
            continue
        if "/" in t or HUB_PATTERNS.search(t):
            continue
        w = get_wikitext(t)
        time.sleep(DELAY)
        if not w:
            continue
        if not game2_ok and re.search(r"\[\[Grounded 2\]\]", w[:600]):
            continue
        ib = match_infobox(w, family)
        rec = {"title": t, "slug": slug(t), "summary": first_sentence(w)}
        if ib:
            _, body = ib
            rec.update(parse_infobox_params(body))
            rec["_ib"] = ib[0]
        else:
            rec["_ib"] = ""
        out.append(rec)
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(titles)}")
    print(f"  kept {len(out)}")
    return out


def scrape_armor_sets() -> list[dict]:
    titles = category_members("Armor")
    print(f"Armor: {len(titles)} members")
    out = []
    for i, t in enumerate(titles):
        if t.startswith("Category:"):
            continue
        if "/" in t or HUB_PATTERNS.search(t):
            continue
        w = get_wikitext(t)
        time.sleep(DELAY)
        if not w:
            continue
        if re.search(r"\[\[Grounded 2\]\]", w[:600]):
            continue
        rec = {"title": t, "slug": slug(t), "pieces": [], "summary": first_sentence(w)}
        # extract tier
        mt = re.search(r"Tier (\d)", w)
        if mt:
            rec["tier"] = mt.group(1)
        # piece cells: Name ... Defense: X ... Resistance: Y%
        Q = "'''"
        for pm in re.finditer(
            Q + r"([^'\n]+?)<br><br>Defense:" + Q + r"\s*<br>\s*([\d.]+)\s*<br>\s*"
            + Q + r"Resistance:" + Q + r"\s*<br>\s*([\d.]+)%",
            w,
        ):
            rec["pieces"].append({"name": pm.group(1).strip(), "defense": float(pm.group(2)), "resist": float(pm.group(3))})
        # effect & set bonus from prose
        me = re.search(r"piece effect, \[\[Status Effects\]\[([^|\]]*)", w)
        if me:
            rec["pieceEffect"] = me.group(1).strip()
        ms = re.search(r"set bonus, \[\[Status Effects\]\[([^|\]]*)", w)
        if ms:
            rec["setBonus"] = ms.group(1).strip()
        # 跳过 wiki 拆分出的导航/概述页（无实际套装数据）
        if t.startswith("Armor ("):
            continue
        out.append(rec)
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(titles)}")
    print(f"  kept {len(out)}, with pieces: {len([r for r in out if r['pieces']])}")
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"

    if which in ("all", "weapons"):
        weapons = scrape_family("Weapons & Tools", "Tools")
        (OUT / "weapons.json").write_text(json.dumps(weapons, ensure_ascii=False, indent=1), encoding="utf-8")

    if which in ("all", "creatures"):
        creatures = scrape_family("Creatures", "Creatures")
        (OUT / "creatures.json").write_text(json.dumps(creatures, ensure_ascii=False, indent=1), encoding="utf-8")

    if which in ("all", "consumables"):
        cons = scrape_family("Consumables", "", game2_ok=False)
        (OUT / "consumables.json").write_text(json.dumps(cons, ensure_ascii=False, indent=1), encoding="utf-8")

    if which in ("all", "trinkets"):
        tr = scrape_family("Trinkets", "Trinkets")
        (OUT / "trinkets.json").write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")

    if which in ("all", "armor"):
        armor = scrape_armor_sets()
        (OUT / "armor.json").write_text(json.dumps(armor, ensure_ascii=False, indent=1), encoding="utf-8")

    print("DONE", which)


if __name__ == "__main__":
    main()
