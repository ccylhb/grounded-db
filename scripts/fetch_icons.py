#!/usr/bin/env python3
"""GroundDB icon fetcher v3 — wiki.gg infoboxes are Lua templates that default
the image to File:<PageName>.png without listing it in wikitext or prop=images.
So: 1) probe File:<Title>.png existence via imageinfo (batched)
    2) fallback: prop=images candidates for pages with no direct hit
    3) download thumbs to public/icons/, patch icon into dataset JSONs."""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

WIKI = "https://grounded.wiki.gg/api.php"
UA = "GroundDB/1.0 (site: grounded-db.pages.dev; contact franceiwhdbks865@gmail.com)"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "src" / "data"
ICON_DIR = ROOT / "public" / "icons"
ICON_DIR.mkdir(parents=True, exist_ok=True)
DELAY = 0.5
BATCH = 50

DATASETS = ["weapons", "creatures", "consumables", "trinkets", "armor"]
JUNK = re.compile(r"Damagetype|Creaturecard|Grounded( 2)? Logo|Status|Ambox|Wiki|\.gif$|\.svg$", re.I)


def api(params: dict, retries: int = 3) -> dict:
    params = {**params, "format": "json"}
    url = WIKI + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(urllib.request.urlopen(req, timeout=30) if False else r)
        except Exception as e:
            print(f"  retry {attempt + 1} ({e})")
            time.sleep(2 * (attempt + 1))
    return {}


def safe_name(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_") + ".png"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 500:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if len(data) < 200:
            return False
        dest.write_bytes(data)
        return True
    except Exception as e:
        print(f"  download fail {dest.name}: {e}")
        return False


def imageinfo_urls(file_titles: list[str]) -> dict[str, str]:
    urls = {}
    for start in range(0, len(file_titles), BATCH):
        chunk = file_titles[start : start + BATCH]
        d = api({"action": "query", "titles": "|".join(chunk),
                 "prop": "imageinfo", "iiprop": "url", "iiurlwidth": "120"})
        for p in d.get("query", {}).get("pages", {}).values():
            ii = p.get("imageinfo")
            if ii:
                urls[p["title"]] = ii[0].get("thumburl") or ii[0].get("url")
        time.sleep(DELAY)
    return urls


def pick(files: list[str], title: str) -> str | None:
    exact = f"File:{title}.png"
    if exact in files:
        return exact
    t = norm(title)
    clean = [f for f in files if not JUNK.search(f)]
    contains = [f for f in clean if t in norm(f.replace("File:", ""))]
    return contains[0] if contains else (clean[0] if clean else None)


def main() -> None:
    items = {}
    for ds in DATASETS:
        for i, it in enumerate(json.load(open(DATA / f"{ds}.json", encoding="utf-8"))):
            items.setdefault(it["title"], []).append((ds, i))
    titles = sorted(items)
    print(f"unique titles: {len(titles)}")

    # step 1: probe File:<Title>.png directly
    exact = [f"File:{t}.png" for t in titles]
    urls = imageinfo_urls(exact)
    print(f"exact-name hits: {len(urls)}/{len(titles)}")

    # step 2: fallback via prop=images for the rest
    missing = [t for t in titles if f"File:{t}.png" not in urls]
    fallback = {}
    for start in range(0, len(missing), BATCH):
        chunk = missing[start : start + BATCH]
        d = api({"action": "query", "prop": "images", "imlimit": "100",
                 "titles": "|".join(chunk)})
        for p in d.get("query", {}).get("pages", {}).values():
            c = pick([im["title"] for im in p.get("images", [])], p["title"])
            if c:
                fallback[p["title"]] = c
        time.sleep(DELAY)
    print(f"fallback candidates: {len(fallback)}/{len(missing)}")

    furls = imageinfo_urls(sorted(set(fallback.values())))
    for t, f in fallback.items():
        if f in furls:
            urls[f"File:{t}.png"] = furls[f]  # treat as direct hit for the item
    print(f"total with url: {len(urls)}/{len(titles)}")

    # step 3: download (keyed by item title)
    ok = 0
    for t in titles:
        url = urls.get(f"File:{t}.png")
        if url and download(url, ICON_DIR / safe_name(t)):
            ok += 1
        time.sleep(0.12)
    print(f"downloaded: {ok}")

    # step 4: patch JSONs
    icon_path = {t: "/icons/" + safe_name(t) for t in titles
                 if (ICON_DIR / safe_name(t)).exists()}
    for ds in DATASETS:
        path = DATA / f"{ds}.json"
        data = json.load(open(path, encoding="utf-8"))
        hit = 0
        for it in data:
            it["icon"] = icon_path.get(it["title"], "")
            if it["icon"]:
                hit += 1
        json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{ds}: {hit}/{len(data)} icons")


if __name__ == "__main__":
    main()
