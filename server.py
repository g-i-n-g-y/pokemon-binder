"""Pokemon Binder - tiny self-hosted collection tracker for BEN.

- Any number of English sets, each in data/sets/<set id>/
- Card lists come from the PokemonTCG/pokemon-tcg-data project on GitHub
- Card images are downloaded to BEN when a set is added
- Prices refresh once a day from TCGplayer recent sales (Unlimited, English, LP/MP)
- TCGdex (free, no key) adds TCGplayer market and Cardmarket prices as a backup and second opinion
Python standard library only. Listens on port 8080 inside the container.

Test one card's price lookup:  docker exec neo-binder python server.py --test neo4-107

Updates: only when you choose them. Settings -> About -> Check for updates shows what's new
from the public GitHub repository (GITHUB_REPO, default g-i-n-g-y/pokemon-binder) and asks
before installing anything. Restarting never installs updates. No key is needed. Set
GITHUB_REPO to an empty value to use a folder mounted at /updates instead (same button). GITHUB_TOKEN is optional and only
needed for a private copy of the repository. Replaced files are kept in previous/.
"""
from html import unescape
import io, json, os, re, shutil, sys, tempfile, threading, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
try:
    from zoneinfo import ZoneInfo
except ImportError:  # very old Python
    ZoneInfo = None

APP_VERSION = "2.19"   # 3.0 big changes, 2.12 features, 2.11.1 small fixes (see CHANGELOG.md)

APP = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(APP, "data")
SETS_DIR = os.path.join(DATA, "sets")
SETS_FILE = os.path.join(DATA, "sets.json")
SETTINGS = os.path.join(DATA, "settings.json")
DEFAULT_SLOTS = [{"t": "raw", "c": "LP"}, {"t": "raw", "c": "MP"}]
DEFAULT_SETTINGS = {"auto": True, "time": "03:00", "tz": "America/New_York", "offset": -240, "lastAuto": "",
                    "slots": DEFAULT_SLOTS, "backup": True}
RAW_CONDS = ("NM", "LP", "MP", "HP", "DMG")
GRADERS = ("PSA", "BGS", "CGC", "SGC", "TAG", "ACE", "Any")
GRADES = ("10", "9.5", "9", "8.5", "8", "7.5", "7", "6", "5", "4", "3", "2", "1")
CATALOG = os.path.join(DATA, "catalog.json")
GH = "https://raw.githubusercontent.com/PokemonTCG/pokemon-tcg-data/master"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
WANT_COND = ("Lightly Played", "Moderately Played")   # updated from the price slots at each refresh
SALES_TO_AVERAGE = 10
DAY = 24 * 3600
MAX_PHOTO = 15 * 1024 * 1024
# Browser tab icon. Your own icon (uploaded in Settings) lives in data/, so it never goes into the repository.
ICON_FILE = os.path.join(DATA, "favicon")
ICON_TYPES = ("image/png", "image/jpeg", "image/webp", "image/gif", "image/x-icon", "image/vnd.microsoft.icon")
MAX_ICON = 2 * 1024 * 1024
DEFAULT_ICON = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect x="6" y="4" width="52" height="56" rx="8" fill="#2A2438"/>
<rect x="13" y="11" width="17" height="22" rx="3" fill="#A88BEA"/><rect x="34" y="11" width="17" height="22" rx="3" fill="#E2B04A"/>
<rect x="13" y="37" width="17" height="17" rx="3" fill="#5CC3CC"/><rect x="34" y="37" width="17" height="17" rx="3" fill="#6B6380"/>
</svg>"""
SID_RE = r"[a-z0-9][a-z0-9.\-]{0,40}"
NUM_RE = r"[A-Za-z0-9\-]{1,24}"
DEX_RE = re.compile(r"dex-(\d{1,4})")   # a Pokémon master set binder, like dex-158 for Totodile
DEX_INDEX = os.path.join(DATA, "dex_index.json")
SPRITES = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"

lock = threading.Lock()
job_lock = threading.Lock()
job = {"running": False, "set": "", "name": "", "done": 0, "total": 0, "priced": 0, "message": ""}
img_jobs = {}
dex_job = {"running": False, "done": 0, "total": 0, "error": ""}
shows_job = {"running": False, "error": "", "done": 0, "total": 0}


# ---------- small helpers ----------

def log(msg):
    print(msg, flush=True)


def read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def sdir(sid, *parts):
    return os.path.join(SETS_DIR, sid, *parts)


def num_key(n):
    m = re.match(r"([A-Za-z]*)(\d+)", n)
    return (m.group(1), int(m.group(2))) if m else (n, 0)


# ---------- set catalog and card lists ----------

def catalog(force=False):
    cat = read_json(CATALOG, None)
    if cat and not force and time.time() - cat.get("fetched", 0) < 7 * DAY:
        return cat["sets"]
    try:
        raw = json.loads(http_get(f"{GH}/sets/en.json"))
        sets = [{"id": s["id"], "name": s["name"], "series": s.get("series", ""),
                 "printedTotal": s.get("printedTotal", 0), "total": s.get("total", 0),
                 "releaseDate": s.get("releaseDate", "")} for s in raw]
        write_json(CATALOG, {"fetched": time.time(), "sets": sets})
        return sets
    except Exception as e:
        log(f"catalog: {e}")
        return cat["sets"] if cat else []


def fetch_cards(sid):
    raw = json.loads(http_get(f"{GH}/cards/en/{sid}.json"))
    cards = []
    for c in raw:
        cards.append({"n": str(c["number"]), "name": c["name"], "rarity": c.get("rarity") or "",
                      "type": c.get("supertype", ""),
                      "img": (c.get("images") or {}).get("large") or (c.get("images") or {}).get("small", "")})
    cards.sort(key=lambda c: num_key(c["n"]))
    write_json(sdir(sid, "cards.json"), cards)
    return cards


def set_cards(sid):
    """Every card in a binder: the card database's list plus any custom cards you added."""
    cards = read_json(sdir(sid, "cards.json"), None)
    if cards is None:
        cards = dex_cards(sid) if is_dex(sid) else fetch_cards(sid)
    return cards + custom_cards(sid)


# ---------- custom cards (ones the card database is missing) ----------
# Saved per binder in custom.json as [{n: "c1", name, set, num, rarity, tcg (TCGplayer product id), price}].
# They get a "c" number so they never clash with real card numbers, and work like any other card.

CUSTOM_N = re.compile(r"c\d{1,5}")


def custom_list(sid):
    out = read_json(sdir(sid, "custom.json"), [])
    return [c for c in out if isinstance(c, dict) and CUSTOM_N.fullmatch(str(c.get("n", "")))] if isinstance(out, list) else []


def custom_cards(sid):
    """Custom cards shaped like database cards. A front photo of your copy doubles as the card picture."""
    out = []
    for c in custom_list(sid):
        n = c["n"]
        out.append({"n": n, "name": c.get("name", ""), "rarity": c.get("rarity", ""), "type": "",
                    "set": c.get("set", ""), "num": c.get("num", ""), "custom": True, "tcg": c.get("tcg"),
                    "img": f"set/{sid}/photo/{n}" if os.path.isfile(sdir(sid, "photos", n)) else ""})
    return out


def tcg_product(v):
    """A TCGplayer product id from a link like tcgplayer.com/product/12345/... or a bare number."""
    t = str(v or "").strip()
    if not t:
        return None
    m = re.search(r"tcgplayer\.com/product/(\d{1,9})", t) or re.fullmatch(r"(\d{1,9})", t)
    if not m:
        raise ValueError("That doesn't look like a TCGplayer card link (it should contain /product/ and a number)")
    return int(m.group(1))


def clean_custom(raw):
    name = str(raw.get("name") or "").strip()[:80]
    if not name:
        raise ValueError("Give the card a name")
    out = {"name": name, "set": str(raw.get("set") or "").strip()[:80], "num": str(raw.get("num") or "").strip()[:20],
           "rarity": str(raw.get("rarity") or "").strip()[:40], "tcg": tcg_product(raw.get("tcg"))}
    price = raw.get("price")
    if price not in (None, ""):
        try:
            price = round(float(str(price).replace("$", "").replace(",", "")), 2)
        except ValueError:
            raise ValueError("The price should be a number, like 4.50")
        if not 0 < price < 1_000_000:
            raise ValueError("The price should be more than $0")
    out["price"] = price or None
    return out


def save_custom(sid, n, raw):
    """Add (n=None) or edit a custom card. Returns the saved card."""
    rec = clean_custom(raw)
    with lock:
        lst = custom_list(sid)
        if n is None:
            if len(lst) >= 500:
                raise ValueError("That's the most custom cards one binder can hold")
            used = {int(c["n"][1:]) for c in lst}
            n = f"c{max(used, default=0) + 1}"
            lst.append(dict(rec, n=n, added=today_local()))
        else:
            old = next((c for c in lst if c["n"] == n), None)
            if not old:
                raise ValueError("That custom card isn't in this binder any more")
            old.update(rec)
        write_json(sdir(sid, "custom.json"), lst)
        # a typed price shows right away; a TCGplayer link fills in on the next price refresh
        prices = read_json(sdir(sid, "prices.json"), {})
        inf = prices.setdefault("info", {}).setdefault(n, {})
        if rec["price"]:
            inf["manual"] = rec["price"]
        else:
            inf.pop("manual", None)
        if n is not None and rec["tcg"] != inf.get("tcgId"):
            for k in ("cond", "recent"):
                inf.pop(k, None)
        inf["tcgId"] = rec["tcg"]
        mp = main_price(inf, set_slots(sid))
        if mp:
            prices.setdefault("p", {})[n] = [mp[0]]
            inf.update(src=mp[3], count=mp[1], last=mp[2])
        else:
            prices.setdefault("p", {}).pop(n, None)
        write_json(sdir(sid, "prices.json"), prices)
    return next(c for c in custom_cards(sid) if c["n"] == n)


def delete_custom(sid, n):
    """Remove a custom card with everything saved for it (copies, purchases, prices, photos)."""
    with lock:
        lst = custom_list(sid)
        if not any(c["n"] == n for c in lst):
            raise ValueError("That custom card isn't in this binder any more")
        write_json(sdir(sid, "custom.json"), [c for c in lst if c["n"] != n])
        for f, key in (("collection.json", None), ("prices.json", "p"), ("prices.json", "info"), ("shop.json", None)):
            d = read_json(sdir(sid, f), {})
            box = d.get(key) if key else d
            if isinstance(box, dict) and n in box:
                box.pop(n)
                write_json(sdir(sid, f), d)
        hist = read_json(sdir(sid, "history.json"), {})
        if any(isinstance(day, dict) and n in day for day in hist.values()):
            for day in hist.values():
                if isinstance(day, dict):
                    day.pop(n, None)
            write_json(sdir(sid, "history.json"), hist)
        for f in (n, n + ".json", n + "_back", n + "_back.json"):
            if os.path.exists(sdir(sid, "photos", f)):
                os.remove(sdir(sid, "photos", f))


def card_ref(sid, c):
    """(card id for price lookups, set name, number printed on the card).
    In a Pokémon master set binder each card remembers its own set."""
    if is_dex(sid) or c.get("custom"):
        return (None if c.get("custom") else c["n"]), c.get("set", ""), c.get("num", c["n"])
    return f"{sid}-{c['n']}", sets_list()["meta"].get(sid, {}).get("name", sid), c["n"]


# ---------- Pokémon master set binders ----------

def is_dex(sid):
    return bool(DEX_RE.fullmatch(sid or ""))


def build_dex_index():
    """One pass over every English set: which cards show each Pokémon (by Pokédex number).
    Takes a minute or two and is saved in data/dex_index.json."""
    with job_lock:
        if dex_job["running"]:
            return
        dex_job.update(running=True, done=0, total=0, error="")
    try:
        sets = sorted(catalog(), key=lambda s: (s.get("releaseDate", ""), s["id"]))
        dex_job["total"] = len(sets)
        log(f"Pokémon list: reading {len(sets)} sets...")
        by_dex, done_sets = {}, []
        for i, st in enumerate(sets):
            dex_job["done"] = i
            try:
                raw = json.loads(http_get(f"{GH}/cards/en/{st['id']}.json"))
            except Exception as e:
                log(f"Pokémon list: {st['id']}: {e}")
                continue
            done_sets.append(st["id"])
            for c in raw:
                if c.get("supertype") != "Pokémon":
                    continue
                n = f"{st['id']}-{c['number']}"
                if not re.fullmatch(NUM_RE, n):
                    continue
                card = {"n": n, "num": str(c["number"]), "set": st["name"], "pt": st.get("printedTotal", 0),
                        "date": st.get("releaseDate", ""), "name": c["name"], "rarity": c.get("rarity") or "",
                        "type": "Pokémon",
                        "img": (c.get("images") or {}).get("large") or (c.get("images") or {}).get("small", "")}
                for d in c.get("nationalPokedexNumbers") or []:
                    by_dex.setdefault(str(d), []).append(card)
            time.sleep(0.1)
        if not done_sets:
            raise RuntimeError("couldn't read any sets")
        names = {}
        for d, cards in by_dex.items():
            counts = {}
            for c in cards:
                counts[c["name"]] = counts.get(c["name"], 0) + 1
            names[d] = min(counts, key=lambda k: (-counts[k], len(k)))
        write_json(DEX_INDEX, {"fetched": time.time(), "sets": done_sets, "names": names, "cards": by_dex})
        dex_job["done"] = len(sets)
        log(f"Pokémon list ready: {len(by_dex)} Pokémon.")
        for sid in sets_list()["order"]:   # new sets may have new cards for your master set binders
            if is_dex(sid):
                dex_cards(sid)
    except Exception as e:
        dex_job["error"] = str(e)
        log(f"Pokémon list failed: {e}")
    finally:
        dex_job["running"] = False


def dex_index():
    return read_json(DEX_INDEX, None)


def dex_stale(idx):
    if not idx:
        return True
    have = set(idx.get("sets") or [])
    return time.time() - idx.get("fetched", 0) > 30 * DAY or any(s["id"] not in have for s in catalog())


def start_dex_index(force=False):
    if not dex_job["running"] and (force or dex_stale(dex_index())):
        threading.Thread(target=build_dex_index, daemon=True).start()


def dex_cards(sid):
    """Every English card for one Pokémon, oldest set first. Saved as the binder's card list."""
    idx = dex_index()
    if not idx:
        raise RuntimeError("The Pokémon list isn't ready yet")
    num = DEX_RE.fullmatch(sid).group(1)
    cards = [dict(c) for c in idx["cards"].get(num, [])]
    seen, out = set(), []
    for c in sorted(cards, key=lambda c: (c["date"], c["set"], num_key(c["num"]))):
        if c["n"] not in seen:
            seen.add(c["n"])
            c["i"] = len(out)
            out.append(c)
    write_json(sdir(sid, "cards.json"), out)
    return out


def sprite_url(num):
    num = int(num)
    if num <= 251:
        return f"{SPRITES}/versions/generation-ii/crystal/transparent/{num}.png"
    if num <= 649:
        return f"{SPRITES}/versions/generation-v/black-white/{num}.png"
    return f"{SPRITES}/{num}.png"


def fetch_sprite(sid):
    """The Pokémon's game sprite (see-through background), saved next to the binder."""
    dest = sdir(sid, "sprite.png")
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return
    try:
        body = http_get(sprite_url(DEX_RE.fullmatch(sid).group(1)))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest + ".tmp", "wb") as f:
            f.write(body)
        os.replace(dest + ".tmp", dest)
    except Exception as e:
        log(f"{sid}: sprite: {e}")


def add_dex(sid):
    idx = dex_index()
    if not idx:
        start_dex_index()
        raise ValueError("The Pokémon list is still being made. Try again in a minute")
    num = DEX_RE.fullmatch(sid).group(1)
    name = (idx.get("names") or {}).get(num)
    if not name:
        raise ValueError("No English cards found for that Pokémon")
    cards = dex_cards(sid)
    meta = {"id": sid, "name": name, "series": "Master set", "dex": int(num), "kind": "dex",
            "printedTotal": 0, "total": len(cards), "releaseDate": ""}
    with lock:
        sl = sets_list()
        if sid not in sl["order"]:
            sl["order"].append(sid)
        sl["meta"][sid] = meta
        write_json(SETS_FILE, sl)
    fetch_sprite(sid)
    start_images(sid)
    threading.Thread(target=refresh_prices, args=(sid, "new binder"), daemon=True).start()
    log(f"Added master set {name} ({len(cards)} cards)")
    return meta


def sets_list():
    return read_json(SETS_FILE, {"order": [], "meta": {}})


def add_set(sid):
    if is_dex(sid):
        return add_dex(sid)
    meta = next((s for s in catalog() if s["id"] == sid), None)
    if not meta:
        raise ValueError("Unknown set")
    cards = set_cards(sid)
    with lock:
        sl = sets_list()
        if sid not in sl["order"]:
            sl["order"].append(sid)
        sl["meta"][sid] = meta
        write_json(SETS_FILE, sl)
    start_images(sid)
    threading.Thread(target=refresh_prices, args=(sid, "new set"), daemon=True).start()
    log(f"Added set {meta['name']} ({len(cards)} cards)")
    return meta


def remove_set(sid):
    with lock:
        sl = sets_list()
        if sid in sl["order"]:
            sl["order"].remove(sid)
        write_json(SETS_FILE, sl)


# ---------- images ----------

def image_path(sid, n):
    return sdir(sid, "images", f"{n}.png")


def fetch_image(sid, card):
    dest = image_path(sid, card["n"])
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return True
    if not card.get("img"):
        return False
    try:
        body = http_get(card["img"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest + ".tmp", "wb") as f:
            f.write(body)
        os.replace(dest + ".tmp", dest)
        return True
    except Exception as e:
        log(f"image {sid}-{card['n']}: {e}")
        return False


def download_images(sid):
    try:
        cards = set_cards(sid)
        missing = [c for c in cards if not os.path.exists(image_path(sid, c["n"]))]
        if not missing:
            return
        log(f"{sid}: downloading {len(missing)} card images...")
        img_jobs[sid] = {"done": 0, "total": len(missing)}
        ok = 0
        for i, c in enumerate(missing):
            img_jobs[sid]["done"] = i
            ok += fetch_image(sid, c)
            time.sleep(0.2)
        log(f"{sid}: card images {ok} of {len(missing)} downloaded.")
    finally:
        img_jobs.pop(sid, None)


def start_images(sid):
    if sid in img_jobs:
        return
    img_jobs[sid] = {"done": 0, "total": 0}
    threading.Thread(target=download_images, args=(sid,), daemon=True).start()


# ---------- prices ----------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


APP_UA = "pokemon-binder (+https://github.com/g-i-n-g-y/pokemon-binder)"


def product_id(card_id, ids, verbose=False):
    """TCGplayer product id, found by following pokemontcg.io's price link for the card.
    Tries a plain app user agent first: a browser-looking one can get blocked as a fake browser."""
    if card_id in ids:
        return ids[card_id]
    for ua in (APP_UA, UA):
        try:
            pid = _product_id(card_id, ua)
        except Exception as e:
            pid = None
            if verbose:
                print(f"  lookup ({'app' if ua == APP_UA else 'browser'} user agent) failed: {e}")
            continue
        if pid:
            ids[card_id] = pid
            return pid
        if verbose:
            print(f"  lookup ({'app' if ua == APP_UA else 'browser'} user agent): no product link")
    return None


def _product_id(card_id, ua):
    opener = urllib.request.build_opener(_NoRedirect)
    url = f"https://prices.pokemontcg.io/tcgplayer/{card_id}"
    for _ in range(6):
        m = re.search(r"/product/(\d+)", urllib.parse.unquote(url))
        if m:
            return int(m.group(1))
        try:
            r = opener.open(urllib.request.Request(url, headers={"User-Agent": ua}), timeout=20)
            body = r.read(200000).decode("utf-8", "ignore")
            m = re.search(r"tcgplayer\.com(?:%2F|/)product(?:%2F|/)(\d+)", body)
            return int(m.group(1)) if m else None
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location")
            if not loc:
                return None
            url = urllib.parse.urljoin(url, loc)
    return None


LP_MP_IDS = [2, 3]  # TCGplayer condition ids: 1 NM, 2 LP, 3 MP, 4 HP, 5 DMG (updated from the price slots)
COND_IDS = {"NM": 1, "LP": 2, "MP": 3, "HP": 4, "DMG": 5}
COND_LONG = {"NM": "Near Mint", "LP": "Lightly Played", "MP": "Moderately Played", "HP": "Heavily Played", "DMG": "Damaged"}
MAX_PAGES = 8


def latest_sales(pid, offset=0, conditions=None):
    body = json.dumps({"conditions": conditions or [], "languages": [1], "variants": [],
                       "listingType": "All", "offset": offset, "limit": 25}).encode()
    req = urllib.request.Request(
        f"https://mpapi.tcgplayer.com/v2/product/{pid}/latestsales", data=body,
        headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json",
                 "Origin": "https://www.tcgplayer.com", "Referer": "https://www.tcgplayer.com/"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("data") or []


def is_match(s):
    return (s.get("condition") in WANT_COND and "1st" not in str(s.get("variant", ""))
            and isinstance(s.get("purchasePrice"), (int, float)))


def collect_sales(pid, conditions, verbose=False):
    """Page through recent sales until we have enough LP/MP Unlimited ones."""
    found, seen, offset = [], set(), 0
    for page in range(MAX_PAGES):
        batch = latest_sales(pid, offset, conditions)
        new = 0
        for x in batch:
            key = (x.get("orderDate"), x.get("purchasePrice"), x.get("condition"), x.get("variant"), x.get("title"))
            if key not in seen:
                seen.add(key)
                found.append(x)
                new += 1
        if verbose:
            print(f"  page {page + 1}: {len(batch)} sales ({new} new): " +
                  ", ".join(f"{x.get('condition')} ${x.get('purchasePrice')}" for x in batch))
        if not batch or not new or sum(map(is_match, found)) >= SALES_TO_AVERAGE:
            break
        offset += len(batch)
        time.sleep(0.3)
    return found


COND_SHORT = {"Near Mint": "NM", "Lightly Played": "LP", "Moderately Played": "MP",
              "Heavily Played": "HP", "Damaged": "DMG"}


def sale_key(x):
    return (x.get("orderDate"), x.get("purchasePrice"), x.get("condition"), x.get("variant"), x.get("title"))


PAGING = {"works": None}   # TCGplayer has been returning the same 5 sales for every page; checked once per run


def condition_sales(pid, verbose=False):
    """Recent sales for each condition (NM, LP, MP, HP, DMG), asked for one condition at a time.
    TCGplayer only returns the newest 5 sales per request, so this gets up to 5 per condition. For the
    conditions your price options use, it also tries a second page in case paging starts working."""
    found, seen = [], set()
    for short, cid in COND_IDS.items():
        offset = 0
        for page in range(2 if (cid in LP_MP_IDS and PAGING["works"] is not False) else 1):
            batch = latest_sales(pid, offset, [cid])
            new = 0
            for x in batch:
                if sale_key(x) not in seen:
                    seen.add(sale_key(x))
                    found.append(x)
                    new += 1
            if verbose:
                print(f"  {short:<3} page {page + 1}: {len(batch)} sales ({new} new): " +
                      ", ".join(f"{(x.get('orderDate') or '')[:10]} ${x.get('purchasePrice')}" for x in batch))
            if page == 1:
                PAGING["works"] = new > 0
            if len(batch) < 5:
                break
            offset += len(batch)
            time.sleep(0.3)
        time.sleep(0.3)
    return found


def lp_mp_sales(pid, verbose=False):
    """All recent sales (for per-condition prices), topped up with LP/MP-only sales if there are too few."""
    if verbose:
        print("All conditions:")
    sales = collect_sales(pid, None, verbose)
    if sum(map(is_match, sales)) < SALES_TO_AVERAGE:
        if verbose:
            print("Topping up with LP/MP-only sales:")
        seen = {sale_key(x) for x in sales}
        for x in collect_sales(pid, LP_MP_IDS, verbose):
            if sale_key(x) not in seen:
                seen.add(sale_key(x))
                sales.append(x)
    return sales


def recent_by_condition(sales, keep=5):
    """{"NM": [[date, price], ...], ...}: the newest Unlimited sales per condition, for the Recent sales tab."""
    out = {}
    for x in sorted(sales, key=lambda x: x.get("orderDate", ""), reverse=True):
        short = COND_SHORT.get(x.get("condition"))
        if short and "1st" not in str(x.get("variant", "")) and isinstance(x.get("purchasePrice"), (int, float)):
            lst = out.setdefault(short, [])
            if len(lst) < keep:
                lst.append([x.get("orderDate", "")[:10], round(x["purchasePrice"], 2)])
    return out


def by_condition(sales):
    """{"NM": [avg, count, latest date], ...} from Unlimited sales, last 10 per condition."""
    groups = {}
    for x in sales:
        short = COND_SHORT.get(x.get("condition"))
        if short and "1st" not in str(x.get("variant", "")) and isinstance(x.get("purchasePrice"), (int, float)):
            groups.setdefault(short, []).append(x)
    out = {}
    for short, xs in groups.items():
        xs.sort(key=lambda x: x.get("orderDate", ""), reverse=True)
        xs = xs[:SALES_TO_AVERAGE]
        out[short] = [round(sum(x["purchasePrice"] for x in xs) / len(xs), 2), len(xs), xs[0].get("orderDate", "")[:10]]
    return out


def lp_mp_average(sales):
    keep = [s for s in sales if is_match(s)]
    keep.sort(key=lambda s: s.get("orderDate", ""), reverse=True)
    keep = keep[:SALES_TO_AVERAGE]
    if not keep:
        return None, 0, None
    avg = round(sum(s["purchasePrice"] for s in keep) / len(keep), 2)
    return avg, len(keep), keep[0].get("orderDate", "")[:10]


# ---------- price slots (what the main price averages) ----------

def clean_slots(raw):
    """Validate the two price slots from Settings. Slot 2 may be None."""
    out = []
    for i, sl in enumerate((raw or [])[:2]):
        if not isinstance(sl, dict) or sl.get("t") == "none":
            if i == 1:
                out.append({"t": "none"})
                continue
            raise ValueError("Slot 1 can't be empty")
        if sl.get("t") == "raw" and sl.get("c") in RAW_CONDS:
            out.append({"t": "raw", "c": sl["c"]})
        elif sl.get("t") == "graded" and sl.get("co") in GRADERS and str(sl.get("g")) in GRADES:
            out.append({"t": "graded", "co": sl["co"], "g": str(sl["g"])})
        else:
            raise ValueError("Unknown price option")
    if not out:
        raise ValueError("Pick at least one price option")
    while len(out) < 2:
        out.append({"t": "none"})
    return out


def slot_key(sl):
    return sl["c"] if sl["t"] == "raw" else f"{sl['co']} {sl['g']}" if sl["t"] == "graded" else ""


def slot_value(info_n, sl):
    """[avg, count, latest] for one slot from a card's stored sales summaries, or None."""
    if sl["t"] == "raw":
        return (info_n.get("cond") or {}).get(sl["c"])
    if sl["t"] == "graded":
        return (info_n.get("graded") or {}).get(slot_key(sl))
    return None


def main_price(info_n, slots, backup=None):
    """The price used in the grid and totals. Both slots raw: their combined average. Otherwise slot 1,
    falling back to slot 2. With no sales for either, TCGplayer's market price from TCGdex (if the
    backup setting is on). Returns (price, count, latest, source) or None."""
    vals = [(sl, slot_value(info_n, sl)) for sl in slots if sl["t"] != "none"]
    if all(sl["t"] == "raw" for sl, _ in vals):
        got = [v for _, v in vals if v]
        if got:
            cnt = sum(v[1] for v in got)
            return (round(sum(v[0] * v[1] for v in got) / cnt, 2), cnt, max(v[2] or "" for v in got), "tcgplayer")
    else:
        for sl, v in vals:
            if v:
                return (v[0], v[1], v[2], "pricecharting" if sl["t"] == "graded" else "tcgplayer")
    if backup is None:
        backup = get_settings().get("backup", True)
    mkt = info_n.get("mkt") or {}
    if backup and mkt.get("tp"):
        return (mkt["tp"], 0, mkt.get("tpUpd") or "", "tcgdex")
    if info_n.get("manual"):
        return (info_n["manual"], 0, "", "manual")   # a price you typed for a custom card
    return None


def set_slots(sid):
    """This binder's two price options. Sets without their own choice use the default from settings.json."""
    own = read_json(sdir(sid, "slots.json"), None)
    if own:
        try:
            return clean_slots(own)
        except ValueError:
            pass
    return get_settings()["slots"]


def wants_graded(slots):
    return any(sl["t"] == "graded" for sl in slots)


def apply_slots(slots):
    """Point the TCGplayer sale collection at the raw conditions the slots use."""
    global WANT_COND, LP_MP_IDS
    raw = [sl["c"] for sl in slots if sl["t"] == "raw"] or ["LP", "MP"]
    WANT_COND = tuple(COND_LONG[c] for c in raw)
    LP_MP_IDS = [COND_IDS[c] for c in raw]


def recompute_prices(sids=None):
    """Recalculate each card's main price from stored sales after the slots change (no downloads).
    Returns True if a graded slot needs data that hasn't been downloaded yet."""
    missing = False
    backup = get_settings().get("backup", True)
    for sid in (sids or list(sets_list()["order"])):
        slots = set_slots(sid)
        with lock:
            prices = read_json(sdir(sid, "prices.json"), {})
            p, info = prices.setdefault("p", {}), prices.get("info") or {}
            for n, inf in info.items():
                if wants_graded(slots) and "graded" not in inf:
                    missing = True
                mp = main_price(inf, slots, backup)
                if mp:
                    p[n] = [mp[0]]
                    inf.update(count=mp[1], last=mp[2], src=mp[3])
                    inf.pop("note", None)
                elif inf.get("src") == "tcgdex":
                    inf["note"] = "No recent sales for your price options; kept last price"
            if info:
                write_json(sdir(sid, "prices.json"), prices)
    return missing


# ---------- graded prices from PriceCharting sold listings ----------

PC = "https://www.pricecharting.com"
GRADE_RE = re.compile(r"\b(PSA|BGS|BECKETT|CGC|SGC|TAG|ACE)\s*(?:GEM\s*MINT\s*|GEM\s*MT\s*|MINT\s*|NM-MT\s*|PRISTINE\s*|BLACK\s*LABEL\s*)?(10|[1-9](?:\.5)?)(?![\d.])", re.I)
SKIP_RE = re.compile(r"1st\s*ed|first\s*edition|shadowless|\blot\b|proxy|custom|reprint|japanese|korean|chinese", re.I)


def slugify(t):
    t = t.lower().replace("é", "e").replace("&", "and").replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def pc_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read().decode("utf-8", "ignore")


def pc_is_card(html, num):
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    title = (m.group(1) if m else "").lower()
    return re.search(rf"#\s*{re.escape(num.lower())}(?![0-9a-z])", title) is not None


def pc_url(sid, card, cache):
    """The PriceCharting page for this card (Unlimited), found once and remembered."""
    key = card["n"]
    if key in cache:
        return cache[key]
    _, set_name, num = card_ref(sid, card)
    tries = [f"{PC}/game/pokemon-{slugify(set_name)}/{slugify(card['name'])}-{slugify(num)}",
             f"{PC}/game/pokemon-{slugify(set_name)}-set/{slugify(card['name'])}-{slugify(num)}"]
    for url in tries:
        try:
            final, html = pc_get(url)
            if "/game/" in final and pc_is_card(html, num):
                cache[key] = final
                return final
        except urllib.error.HTTPError:
            pass
    # fall back to PriceCharting's own search
    q = urllib.parse.quote_plus(f"pokemon {set_name} {card['name']} {num}")
    final, html = pc_get(f"{PC}/search-products?type=prices&q={q}")
    if "/game/" in final and pc_is_card(html, num):
        cache[key] = final
        return final
    for path in re.findall(r'href="(/game/pokemon-[^"/]+/[^"#?]+)"', html):
        if "1st-edition" in path or "japanese" in path:
            continue
        if path.endswith("-" + slugify(num)):
            cache[key] = PC + path
            return PC + path
    cache[key] = ""
    return ""


def pc_sales(html):
    """Sold listings on a PriceCharting card page: [{d, title, price}], newest first."""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row)).strip()
        m = re.match(r"(\d{4}-\d{2}-\d{2}|[A-Z][a-z]{2,8}\.? \d{1,2},? \d{4})\s+(.*?)\s+\$([\d,]+\.\d{2})\b", text)
        if m:
            d = m.group(1)
            if not d[0].isdigit():
                try:
                    d = datetime.strptime(d.replace(".", "").replace(",", "")[:3] + " " + " ".join(d.replace(",", "").split()[1:]), "%b %d %Y").strftime("%Y-%m-%d")
                except ValueError:
                    continue
            out.append({"d": d, "title": m.group(2), "price": float(m.group(3).replace(",", ""))})
    seen, uniq = set(), []
    for x in out:
        k = (x["d"], x["title"], x["price"])
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return sorted(uniq, key=lambda x: x["d"], reverse=True)


def graded_recent(sales, keep=5):
    """{"PSA 9": [[date, price, title], ...]}: newest graded sales per company and grade."""
    out = {}
    for x in sales:
        if SKIP_RE.search(x["title"]):
            continue
        m = GRADE_RE.search(x["title"])
        if m:
            key = f"{m.group(1).upper().replace('BECKETT', 'BGS')} {m.group(2)}"
            lst = out.setdefault(key, [])
            if len(lst) < keep:
                lst.append([x["d"], x["price"]])
    return out


def graded_groups(sales):
    """{"PSA 9": [avg, count, latest], ..., "Any 9": [...]} from graded Unlimited sales, last 10 each."""
    groups = {}
    for x in sales:
        if SKIP_RE.search(x["title"]):
            continue
        m = GRADE_RE.search(x["title"])
        if not m:
            continue
        co = m.group(1).upper().replace("BECKETT", "BGS")
        g = m.group(2)
        for key in (f"{co} {g}", f"Any {g}"):
            groups.setdefault(key, []).append(x)
    out = {}
    for key, xs in groups.items():
        xs = sorted(xs, key=lambda x: x["d"], reverse=True)[:SALES_TO_AVERAGE]
        out[key] = [round(sum(x["price"] for x in xs) / len(xs), 2), len(xs), xs[0]["d"]]
    return out


def graded_for(sid, card, cache):
    url = pc_url(sid, card, cache)
    if not url:
        return None, "", {}
    _, html = pc_get(url)
    sales = pc_sales(html)
    return graded_groups(sales), url, graded_recent(sales)


# ---------- market prices from TCGdex (free backup and cross-check) ----------
# TCGdex is a free card API (no key) that includes TCGplayer's market price and Cardmarket's averages
# in every card. The binder stores them as a second opinion, and uses TCGplayer's market price as the
# card's price when there are no recent sales for your price options (Settings -> Price average).

TCGDEX = "https://api.tcgdex.net/v2/en"
TCGDEX_SETS = {"fetched": 0, "byname": {}}


def tcgdex_get(path):
    req = urllib.request.Request(TCGDEX + path, headers={"User-Agent": APP_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def tcgdex_set_id(set_name):
    """TCGdex's id for a set, matched by name (their ids don't always match the card database's)."""
    if time.time() - TCGDEX_SETS["fetched"] > DAY:
        try:
            TCGDEX_SETS["byname"] = {s.get("name", "").lower(): s["id"] for s in tcgdex_get("/sets") if s.get("id")}
            TCGDEX_SETS["fetched"] = time.time()
        except Exception as e:
            log(f"TCGdex sets: {e}")
    return TCGDEX_SETS["byname"].get((set_name or "").lower())


def tcgdex_card(sid, card, cache):
    """The TCGdex card for one binder card, or None. Found ids are remembered in tcgdex_ids.json."""
    card_id, set_name, num = card_ref(sid, card)
    if cache.get(card["n"]):
        try:
            return tcgdex_get("/cards/" + urllib.parse.quote(cache[card["n"]]))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            cache.pop(card["n"], None)
    tries = ["/cards/" + urllib.parse.quote(card_id)]
    tid = tcgdex_set_id(set_name)
    if tid:
        tries += [f"/sets/{urllib.parse.quote(tid)}/{urllib.parse.quote(x)}"
                  for x in dict.fromkeys([num, num.zfill(3) if num.isdigit() else num])]
    for path in tries:
        try:
            got = tcgdex_get(path)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        if isinstance(got, dict) and got.get("id"):
            cache[card["n"]] = got["id"]
            return got
    return None


FX_FILE = os.path.join(DATA, "fx.json")


def eur_to_usd():
    """Today's euro to US dollar rate from Frankfurter (European Central Bank rates, free, no key).
    Saved in data/fx.json and reused for a day; an older saved rate is used if the site can't be reached."""
    fx = read_json(FX_FILE, {})
    if fx.get("usd") and time.time() - fx.get("fetched", 0) < DAY:
        return fx["usd"]
    for url in ("https://api.frankfurter.dev/v1/latest?base=EUR&symbols=USD",
                "https://api.frankfurter.app/latest?from=EUR&to=USD"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": APP_UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                usd = float((json.load(r).get("rates") or {}).get("USD") or 0)
            if 0.5 < usd < 3:
                write_json(FX_FILE, {"usd": usd, "fetched": time.time()})
                return usd
        except Exception as e:
            log(f"exchange rate: {e}")
    return fx.get("usd")


def _num(v):
    return round(float(v), 2) if isinstance(v, (int, float)) and v > 0 else None


def tcgdex_market(tc, rarity="", usd=None):
    """{"tp": TCGplayer market USD, "tpLow", "tpVar", "tpUpd", "cm30": Cardmarket 30-day avg in USD, "cmTrend", "cmUpd"}
    Cardmarket prices are in euros, so they're converted with `usd` (euro to dollar rate) or left out without one.
    from a TCGdex card. Skips 1st Edition prices; prefers Unlimited, then holo or normal to match the card."""
    pr = (tc or {}).get("pricing") or {}
    out = {}
    tp = pr.get("tcgplayer") or {}
    vars_ = {k: v for k, v in tp.items() if isinstance(v, dict) and not re.search(r"1st|first", k, re.I)
             and _num(v.get("marketPrice") or v.get("midPrice"))}
    if vars_:
        holo = "holo" in (rarity or "").lower()

        def rank(k):
            kl = k.lower()
            return ("reverse" in kl,
                    ("holo" in kl) != holo,
                    "unlimited" not in kl)
        k = sorted(vars_, key=rank)[0]
        v = vars_[k]
        price = _num(v.get("marketPrice")) or _num(v.get("midPrice"))
        low = _num(v.get("lowPrice"))
        out.update(tp=price, tpLow=low if low and low <= price else None,   # a "low" above market is bad data
                   tpVar=k, tpUpd=str(tp.get("updated") or "")[:10])
    cm = pr.get("cardmarket") or {}
    if usd and (_num(cm.get("avg30")) or _num(cm.get("trend"))):
        conv = lambda v: round(v * usd, 2) if v else None
        out.update(cm30=conv(_num(cm.get("avg30"))), cmTrend=conv(_num(cm.get("trend"))),
                   cmUpd=str(cm.get("updated") or "")[:10], cmUsd=True)
    return out


def refresh_prices(sid, reason="daily"):
    with job_lock:
        if job["running"]:
            return False
        name = sets_list()["meta"].get(sid, {}).get("name", sid)
        job.update(running=True, set=sid, name=name, done=0, total=0, priced=0, message="")
    try:
        cards = set_cards(sid)
        job["total"] = len(cards)
        log(f"{sid}: price refresh started ({reason}).")
        ids = read_json(sdir(sid, "tcg_ids.json"), {})
        slots = set_slots(sid)
        apply_slots(slots)
        PAGING["works"] = None
        graded_on = wants_graded(slots)
        pc_cache = read_json(sdir(sid, "pc_urls.json"), {})
        backup = get_settings().get("backup", True)
        dex_ids = read_json(sdir(sid, "tcgdex_ids.json"), {})
        usd = eur_to_usd() if backup else None
        with lock:
            prices = read_json(sdir(sid, "prices.json"), {})
        p = prices.setdefault("p", {})
        info = prices.setdefault("info", {})
        priced = 0
        for i, c in enumerate(cards):
            job["done"] = i
            n = c["n"]
            inf = dict(info.get(n) or {})
            try:
                if c.get("custom"):
                    pid = c.get("tcg")
                    inf["tcgId"] = pid
                else:
                    pid = product_id(card_ref(sid, c)[0], ids)
                if pid:
                    sales = condition_sales(pid)
                    inf["cond"] = by_condition(sales)
                    inf["recent"] = recent_by_condition(sales)
                elif not c.get("custom"):
                    log(f"{sid}-{n}: no TCGplayer product found")
            except Exception as e:
                log(f"{sid}-{n}: TCGplayer: {e}")
            if graded_on:
                try:
                    time.sleep(1)
                    groups, url, grecent = graded_for(sid, c, pc_cache)
                    if groups is not None:
                        inf["graded"], inf["pc"], inf["gradedRecent"] = groups, url, grecent
                    else:
                        inf["graded"] = {}
                        log(f"{sid}-{n}: no PriceCharting page found")
                except Exception as e:
                    log(f"{sid}-{n}: PriceCharting: {e}")
            if backup and not c.get("custom"):
                try:
                    tc = tcgdex_card(sid, c, dex_ids)
                    if tc:
                        mkt = tcgdex_market(tc, c.get("rarity", ""), usd)
                        if mkt:
                            inf["mkt"] = mkt
                    else:
                        log(f"{sid}-{n}: no TCGdex card found")
                except Exception as e:
                    log(f"{sid}-{n}: TCGdex: {e}")
            mp = main_price(inf, slots, backup)
            if mp:
                p[n] = [mp[0]]
                inf.update(src=mp[3], count=mp[1], last=mp[2])
                inf.pop("note", None)
                priced += 1
                job["priced"] = priced
            else:
                inf["note"] = "No recent sales for your price options; kept last price"
            info[n] = inf
            time.sleep(1)
        job["done"] = len(cards)
        write_json(sdir(sid, "tcg_ids.json"), ids)
        if graded_on:
            write_json(sdir(sid, "pc_urls.json"), pc_cache)
        if backup:
            write_json(sdir(sid, "tcgdex_ids.json"), dex_ids)
        prices["lastRun"] = int(time.time())
        if priced:
            prices["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with lock:
            write_json(sdir(sid, "prices.json"), prices)
            snapshot_history(sid, prices)
        job["message"] = f"{name}: updated {priced} of {len(cards)} prices."
        log(f"{sid}: price refresh done, {priced} of {len(cards)} priced.")
    except Exception as e:
        job["message"] = f"Price refresh failed: {e}"
        log(f"{sid}: price refresh failed: {e}")
    finally:
        job["running"] = False
    return True


def get_settings():
    st = dict(DEFAULT_SETTINGS)
    st.update(read_json(SETTINGS, {}))
    return st


def local_now(st):
    """Current time in the time zone chosen in Settings (falls back to the saved UTC offset)."""
    if ZoneInfo:
        try:
            return datetime.now(ZoneInfo(st["tz"]))
        except Exception:
            pass
    return datetime.now(timezone(timedelta(minutes=int(st.get("offset", 0)))))


def next_run(st):
    now = local_now(st)
    h, m = map(int, st["time"].split(":"))
    run = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if now >= run or st.get("lastAuto") == now.strftime("%Y-%m-%d"):
        run += timedelta(days=1)
    return run


def refresh_all(reason):
    for sid in list(sets_list()["order"]):
        while job["running"]:
            time.sleep(15)
        refresh_prices(sid, reason)


# ---------- price history, purchases, spending ----------

def today_local():
    return local_now(get_settings()).strftime("%Y-%m-%d")


def snapshot_history(sid, prices=None):
    """Save today's LP/MP price for every card (one entry per day; the latest refresh wins)."""
    prices = prices if prices is not None else read_json(sdir(sid, "prices.json"), {})
    p = prices.get("p") or {}
    if not p:
        return
    hist = read_json(sdir(sid, "history.json"), {})
    hist[today_local()] = {n: v[0] for n, v in p.items() if v and isinstance(v[0], (int, float))}
    write_json(sdir(sid, "history.json"), hist)


def migrate_purchases(sid):
    """Older records kept one 'cost' number; turn it into an undated purchase."""
    with lock:
        coll = read_json(sdir(sid, "collection.json"), {})
        changed = False
        for rec in coll.values():
            if not isinstance(rec, dict):
                continue
            if "cost" in rec:
                cost = rec.pop("cost")
                if isinstance(cost, (int, float)) and cost > 0 and not rec.get("purchases"):
                    rec["purchases"] = [{"d": "", "price": cost, "where": ""}]
                changed = True
            # copies owned always equals the number of purchases; pad older cards with "before tracking" rows
            buys = [b for b in (rec.get("purchases") or []) if isinstance(b, dict)]
            q = int(rec.get("qty") or 0)
            if q > len(buys):
                buys = [{"d": "", "price": None, "where": ""} for _ in range(q - len(buys))] + buys
            if rec.get("purchases") != buys or q != len(buys):
                rec["purchases"] = buys
                rec["qty"] = len(buys)
                changed = True
        if changed:
            write_json(sdir(sid, "collection.json"), coll)


def spending():
    sl = sets_list()
    log_rows, months = [], {}
    total_spent = 0.0
    undated = 0
    owned = []  # (sid, n, qty, acquired date or "", ratio)
    dates = set()
    hist_by_set, cur_by_set = {}, {}
    for sid in sl["order"]:
        coll = read_json(sdir(sid, "collection.json"), {})
        cards = {c["n"]: c["name"] for c in (read_json(sdir(sid, "cards.json"), None) or [])}
        prices = read_json(sdir(sid, "prices.json"), {})
        base = {n: v[0] for n, v in (prices.get("p") or {}).items() if v}
        info = prices.get("info") or {}
        hist = read_json(sdir(sid, "history.json"), {})
        hist_by_set[sid] = sorted(hist.items())
        cur_by_set[sid] = base
        dates.update(hist.keys())
        set_name = sl["meta"].get(sid, {}).get("name", sid)
        for n, rec in coll.items():
            if not isinstance(rec, dict):
                continue
            buys = [b for b in rec.get("purchases") or [] if isinstance(b, dict)]
            for b in buys:
                price = b.get("price") if isinstance(b.get("price"), (int, float)) else 0
                d = b.get("d") or ""
                total_spent += price
                if d:
                    m = months.setdefault(d[:7], {"m": d[:7], "spent": 0.0, "count": 0})
                    m["spent"] += price
                    m["count"] += 1
                else:
                    undated += 1
                log_rows.append({"set": sid, "setName": set_name, "n": n, "name": cards.get(n, n),
                                 "d": d, "where": b.get("where", ""), "price": price,
                                 "seller": b.get("seller") if isinstance(b.get("seller"), dict) else None})
            q = rec.get("qty") or 0
            if q > 0:
                dated = sorted(b["d"] for b in buys if b.get("d"))
                cond = rec.get("cond")
                cp = ((info.get(n) or {}).get("cond") or {}).get(cond) if cond else None
                b0 = base.get(n) or 0
                ratio = (cp[0] / b0) if (cp and b0) else 1.0
                owned.append((sid, n, q, dated[0] if dated else "", ratio))

    def price_at(sid, n, d):
        val = None
        for hd, snap in hist_by_set[sid]:
            if hd > d:
                break
            if n in snap:
                val = snap[n]
        return val if val is not None else cur_by_set[sid].get(n, 0)

    today = today_local()
    dates.add(today)
    timeline = []
    for d in sorted(dates):
        spent = sum(r["price"] for r in log_rows if not r["d"] or r["d"] <= d)
        value = 0.0
        for sid, n, q, acq, ratio in owned:
            if not acq or acq <= d:
                p = cur_by_set[sid].get(n, 0) if d == today else price_at(sid, n, d)
                value += p * ratio * q
        timeline.append({"d": d, "spent": round(spent, 2), "value": round(value, 2)})
    log_rows.sort(key=lambda r: (r["d"] or "0000"), reverse=True)
    return {"totals": {"spent": round(total_spent, 2), "value": timeline[-1]["value"] if timeline else 0,
                       "undated": undated, "purchases": len(log_rows)},
            "months": [dict(m, spent=round(m["spent"], 2)) for m in sorted(months.values(), key=lambda m: m["m"])],
            "timeline": timeline, "log": log_rows, "today": today}


def scheduler():
    time.sleep(15)
    ticks = 0
    while True:
        if ticks % 30 == 0:
            for sid in list(sets_list()["order"]):
                start_images(sid)  # retries any images that failed earlier
            if os.path.exists(DEX_INDEX):
                start_dex_index()  # picks up new sets for master set binders (about once a month)
            if shows_due() and not shows_job["running"]:
                threading.Thread(target=scan_shows, args=("weekly",), daemon=True).start()
        ticks += 1
        try:
            st = get_settings()
            now = local_now(st)
            today = now.strftime("%Y-%m-%d")
            h, m = map(int, st["time"].split(":"))
            due = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if st["auto"] and now >= due and st.get("lastAuto") != today:
                st["lastAuto"] = today
                with lock:
                    cur = read_json(SETTINGS, {})
                    cur["lastAuto"] = today
                    write_json(SETTINGS, cur)
                log(f"Scheduled price refresh ({st['time']} {st['tz']}).")
                refresh_all("scheduled")
        except Exception as e:
            log(f"scheduler: {e}")
        time.sleep(60)


# ---------- first start: move the original Neo Destiny files into data/sets/neo4 ----------

def setup():
    os.makedirs(SETS_DIR, exist_ok=True)
    old = {"collection.json": "collection.json", "prices.json": "prices.json",
           "tcg_ids.json": "tcg_ids.json", "images": "images", "photos": "photos"}
    if os.path.exists(os.path.join(DATA, "collection.json")) and not os.path.exists(sdir("neo4")):
        os.makedirs(sdir("neo4"), exist_ok=True)
        for src, dst in old.items():
            if os.path.exists(os.path.join(DATA, src)):
                shutil.move(os.path.join(DATA, src), sdir("neo4", dst))
        # photos were saved as data/photos/<n>; keep that layout under the set
        log("Moved Neo Destiny data into data/sets/neo4")
    sl = sets_list()
    if not sl["order"]:
        # first run on a fresh install, or right after the move above
        if not os.path.exists(sdir("neo4", "collection.json")):
            for name, dest in (("seed_collection.json", "collection.json"), ("seed_prices.json", "prices.json")):
                src = os.path.join(APP, name)
                if os.path.exists(src):
                    os.makedirs(sdir("neo4"), exist_ok=True)
                    shutil.copy(src, sdir("neo4", dest))
        sl = {"order": ["neo4"], "meta": {"neo4": {"id": "neo4", "name": "Neo Destiny", "series": "Neo",
              "printedTotal": 105, "total": 113, "releaseDate": "2002/02/28"}}}
        write_json(SETS_FILE, sl)


# ---------- local card shows (from treasurehunter.show) ----------

SHOWS_FILE = os.path.join(DATA, "shows.json")
TH = "https://www.treasurehunter.show"
DEFAULT_AREAS = ["Richmond", "Midlothian", "Chesterfield", "Chester", "Glen Allen", "Henrico", "Short Pump",
                 "Mechanicsville", "Ashland", "Petersburg", "Colonial Heights", "Hopewell", "Powhatan", "Sandston"]
SHOW_RE = re.compile(r'/show/([a-z0-9-]+?)-va-(\d{4}-\d{2}-\d{2})(?=["\'#?/])')
TCG_RE = re.compile(r"pok[eé]?mon|pokmon|\btcg\b|trading card game", re.I)


def area_slug(name):
    return slugify(name)


def shows_state():
    st = read_json(SHOWS_FILE, {})
    st.setdefault("shows", {})
    st.setdefault("areas", DEFAULT_AREAS)
    st.setdefault("auto", True)
    return st


def tidy_show(rec):
    """Drop the town and date the site adds to every title and description (the panel already shows them)."""
    name = re.sub(r"\s+[—–-]\s+[^—–]*,\s*(?:VA|Virginia)\b[^—–]*$", "", rec.get("name", "")).strip()
    desc = re.sub(r"^.*?\bin [^.]*?,\s*Virginia on [A-Z][a-z]+\.? \d{1,2}, \d{4}\.\s*", "", rec.get("desc", "")).strip()
    return dict(rec, name=name or rec.get("name", ""), desc=desc)


def show_details(url):
    """Name, description and image from one show's page (only fetched the first time it's seen)."""
    _, html = pc_get(url)
    def meta(prop):
        m = re.search(rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']*)', html, re.I) or \
            re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']{prop}["\']', html, re.I)
        return unescape(m.group(1)).strip() if m else ""
    title = meta("og:title")
    if not title:
        m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
        title = unescape(m.group(1)).strip() if m else ""
    title = re.split(r"\s+[|·–-]\s+Treasure Hunter", title)[0].strip()
    return {"name": title, "desc": meta("og:description") or meta("description")}


def scan_shows(reason="manual"):
    """Read the Virginia show pages for each area, keep shows in those towns, remember new ones."""
    with job_lock:
        if shows_job["running"]:
            return False
        shows_job.update(running=True, error="", done=0, total=0)
    try:
        st = shows_state()
        areas = [a for a in st["areas"] if area_slug(a)]
        slugs = {area_slug(a): a for a in areas}
        pages = [f"{TH}/shows/virginia"] + [f"{TH}/shows/virginia/{s}" for s in slugs]
        found, ok = {}, 0
        shows_job["total"] = len(pages)
        for i, url in enumerate(pages):
            shows_job["done"] = i
            try:
                _, html = pc_get(url)
                ok += 1
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    log(f"card shows: {url}: {e}")
                continue
            except Exception as e:
                log(f"card shows: {url}: {e}")
                continue
            for slug, d in SHOW_RE.findall(html):
                town = next((s for s in sorted(slugs, key=len, reverse=True) if slug.endswith("-" + s) or slug == s), None)
                if town:
                    found[f"{slug}-va-{d}"] = {"town": slugs[town], "date": d, "slug": slug[: -len(town)].strip("-")}
            time.sleep(1)
        if not ok:
            raise RuntimeError("couldn't reach treasurehunter.show")
        now = now_iso()
        shows = st["shows"]
        new = 0
        shows_job.update(done=len(pages), total=len(pages) + sum(1 for k in found if k not in shows))
        for key, f in found.items():
            if key in shows:
                shows[key]["seen"] = now
                continue
            url = f"{TH}/show/{key}"
            rec = {"url": url, "date": f["date"], "town": f["town"], "first": now, "seen": now,
                   "name": f["slug"].replace("-", " ").title(), "desc": ""}
            try:
                det = show_details(url)
                rec["name"] = det["name"] or rec["name"]
                rec["desc"] = det["desc"][:300]
                time.sleep(1)
            except Exception as e:
                log(f"card shows: {url}: {e}")
            rec["tcg"] = bool(TCG_RE.search(rec["name"] + " " + rec["desc"] + " " + key))
            shows[key] = rec
            new += 1
            shows_job["done"] += 1
        today = today_local()
        st["shows"] = {k: v for k, v in shows.items() if v["date"] >= today}   # drop past shows
        st.setdefault("firstScan", now)   # shows found on the very first scan aren't marked new
        st.update(scanned=now, lastNew=new, error="")
        with lock:
            write_json(SHOWS_FILE, st)
        log(f"Card shows scan ({reason}): {len(found)} in your area, {new} new.")
    except Exception as e:
        shows_job["error"] = str(e)
        with lock:
            st = shows_state()
            st["error"] = str(e)
            write_json(SHOWS_FILE, st)
        log(f"Card shows scan failed: {e}")
    finally:
        shows_job["running"] = False
    return True


def shows_due():
    st = shows_state()
    if not st.get("auto"):
        return False
    last = st.get("scanned", "")
    try:
        age = time.time() - datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return True
    return age > 7 * DAY


# ---------- totals per set (for the all-binders summary) ----------

def set_totals(sid):
    """Same math as the page header: value counts owned copies at their condition's price when set."""
    coll = read_json(sdir(sid, "collection.json"), {})
    cards = (read_json(sdir(sid, "cards.json"), None) or []) + custom_list(sid)
    prices = read_json(sdir(sid, "prices.json"), {})
    p, info = prices.get("p") or {}, prices.get("info") or {}
    t = {"owned": 0, "count": len(cards), "value": 0.0, "paid": 0.0, "need": 0.0, "full": 0.0}
    for c in cards:
        n = c["n"]
        base = (p.get(n) or [0])[0] or 0
        rec = coll.get(n) if isinstance(coll.get(n), dict) else {}
        t["full"] += base
        t["paid"] += sum(b.get("price") for b in rec.get("purchases") or []
                         if isinstance(b, dict) and isinstance(b.get("price"), (int, float)))
        q = rec.get("qty") or 0
        if q > 0:
            t["owned"] += 1
            cp = ((info.get(n) or {}).get("cond") or {}).get(rec.get("cond")) if rec.get("cond") else None
            t["value"] += ((cp[0] if cp else 0) or base) * q
        else:
            t["need"] += base
    return {k: round(v, 2) if isinstance(v, float) else v for k, v in t.items()}


# ---------- spreadsheet import (Excel .xlsx or .csv) ----------
# Reads a card list like the Neo Destiny tracker spreadsheet: a header row with a card number column
# ("Set #", "No.", "Number") and any of Qty / Status, Condition, Your Cost, Notes. Only adds: cards the
# file lists as owned are marked owned; nothing is marked needed and nothing already logged is removed.

MAX_IMPORT = 10 * 1024 * 1024
XNS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
HEADERS = {
    "num": ("set#", "setno", "setnumber", "number", "no", "#", "cardnumber", "cardno", "num", "card#"),
    "name": ("cardname", "name", "card", "pokemon"),
    "qty": ("qty", "quantity", "copies", "count", "owned#", "have"),
    "status": ("status", "owned", "own"),
    "cond": ("condition", "cond"),
    "cost": ("yourcost", "cost", "paid", "pricepaid", "purchaseprice", "buyprice", "costeach"),
    "note": ("notes", "note", "comments", "comment"),
}


def _hkey(t):
    return re.sub(r"[^a-z0-9#]", "", str(t or "").lower())


def _xml(z, name, limit=30 * 1024 * 1024):
    import xml.etree.ElementTree as ET
    if z.getinfo(name).file_size > limit:
        raise ValueError("That spreadsheet is too big")
    data = z.read(name)
    if b"<!DOCTYPE" in data[:2000].upper() or b"<!ENTITY" in data[:2000].upper():
        raise ValueError("That spreadsheet can't be read")
    return ET.fromstring(data)


def _col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(raw):
    """Every sheet in an .xlsx as {sheet name: [[cell, ...], ...]}, using Python's built-in zip and XML tools."""
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise ValueError("That file isn't an Excel spreadsheet or CSV")
    with z:
        names = set(z.namelist())
        if "xl/workbook.xml" not in names:
            raise ValueError("That file isn't an Excel spreadsheet or CSV")
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in _xml(z, "xl/sharedStrings.xml").iter(XNS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(XNS + "t")))
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for r in _xml(z, "xl/_rels/workbook.xml.rels"):
                rels[r.get("Id")] = r.get("Target", "")
        out = {}
        for sh in _xml(z, "xl/workbook.xml").iter(XNS + "sheet"):
            target = rels.get(sh.get(RNS + "id"), "")
            path = target.lstrip("/") if target.startswith("/") else "xl/" + target
            if path not in names:
                continue
            rows = []
            for row in _xml(z, path).iter(XNS + "row"):
                cells = {}
                for c in row.iter(XNS + "c"):
                    t, v = c.get("t"), c.find(XNS + "v")
                    if t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(XNS + "t"))
                    elif v is None or v.text is None:
                        val = None   # a formula Excel hasn't saved a result for
                    elif t == "s":
                        val = shared[int(v.text)] if v.text.isdigit() and int(v.text) < len(shared) else ""
                    elif t in ("str", "e"):
                        val = v.text
                    elif t == "b":
                        val = v.text == "1"
                    else:
                        try:
                            val = float(v.text)
                        except ValueError:
                            val = v.text
                    if c.get("r"):
                        cells[_col(c.get("r"))] = val
                if cells:
                    rows.append([cells.get(i) for i in range(max(cells) + 1)])
                if len(rows) > 5000:
                    break
            out[sh.get("name", "")] = rows
        return out


def read_sheet(raw):
    """The card rows of a spreadsheet: [{"row": line number, "num", "name", "qty", "status", "cond", "cost", "note"}]."""
    import csv
    if raw[:2] == b"PK":
        sheets = read_xlsx(raw)
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        sheets = {"csv": list(csv.reader(io.StringIO(text)))}
    for rows in sheets.values():
        for hi, header in enumerate(rows[:10]):
            keys = [_hkey(h) for h in header]
            cols = {}
            for field, names in HEADERS.items():
                for i, k in enumerate(keys):
                    if k in names and i not in cols.values():
                        cols[field] = i
                        break
            if "num" not in cols or not ({"qty", "status"} & set(cols)):
                continue
            out = []
            for li, r in enumerate(rows[hi + 1:], start=hi + 2):
                get = lambda f: r[cols[f]] if f in cols and cols[f] < len(r) else None
                if get("num") in (None, ""):
                    continue
                out.append({"row": li, **{f: get(f) for f in HEADERS}})
            return out
    raise ValueError("Couldn't find the card list. The file needs a header row with a card number column "
                     "(like \"Set #\") and a Qty or Status column.")


def _clean_num(v):
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    t = str(v).strip().lstrip("#").split("/")[0].strip()
    if CUSTOM_N.fullmatch(t.lower()):
        return t.lower()
    return t.lstrip("0") or t if t.isdigit() else t


def _simple(t):
    t = str(t or "").lower().replace("é", "e").replace("♀", "f").replace("♂", "m")
    return re.sub(r"[^a-z0-9]", "", t)


def same_name(a, b):
    """Card names match, allowing small spelling differences (like Imposter / Impostor)."""
    import difflib
    a, b = _simple(a), _simple(b)
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def _money(v):
    if v in (None, ""):
        return None
    try:
        f = float(str(v).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None
    return round(f, 2) if f > 0 else None


def import_plan(sid, rows):
    """What importing these rows would change, without changing anything."""
    if is_dex(sid):
        raise ValueError("Spreadsheet import works for set binders, not Pokémon master sets")
    cards = {c["n"]: c for c in set_cards(sid)}
    coll = read_json(sdir(sid, "collection.json"), {})
    changes, skipped, already, need = [], [], 0, 0
    seen = set()
    for r in rows:
        n = _clean_num(r["num"])
        card = cards.get(n)
        if not card:
            skipped.append({"row": r["row"], "why": f"No card number {r['num']} in this set"})
            continue
        if r.get("name") and not same_name(r["name"], card["name"]):
            skipped.append({"row": r["row"], "why": f"#{n} is {card['name']} here, but the file says {r['name']}"})
            continue
        if n in seen:
            skipped.append({"row": r["row"], "why": f"#{n} is listed twice; the first row was used"})
            continue
        seen.add(n)
        qty = None
        if r.get("qty") not in (None, ""):
            try:
                qty = max(0, int(float(str(r["qty"]).strip())))
            except ValueError:
                skipped.append({"row": r["row"], "why": f"Qty \"{r['qty']}\" isn't a number"})
                continue
        elif str(r.get("status") or "").strip().lower() in ("owned", "own", "yes", "y", "true", "x", "1"):
            qty = 1
        if not qty:
            need += 1
            continue
        rec = coll.get(n) or {}
        have = int(rec.get("qty") or 0)
        cond = str(r.get("cond") or "").strip().upper()
        cond = cond if cond in RAW_CONDS else ""
        cost = _money(r.get("cost"))
        note = str(r.get("note") or "").strip()[:500]
        add = max(0, qty - have)
        ch = {"n": n, "name": card["name"], "qty": qty, "have": have, "add": add}
        if cond and not rec.get("cond"):
            ch["cond"] = cond
        if note and not rec.get("note"):
            ch["note"] = note
        if cost and add and have == 0:
            ch["each"] = round(cost / qty, 2)   # "Your Cost" is what you paid for all your copies
        if add or "cond" in ch or "note" in ch:
            changes.append(ch)
        else:
            already += 1
    return {"changes": changes, "skipped": skipped[:50], "skippedCount": len(skipped),
            "already": already, "need": need, "rows": len(rows)}


def import_template(sid):
    """A CSV of every card in the binder with what's already saved, ready to fill in and import."""
    import csv
    coll = read_json(sdir(sid, "collection.json"), {})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Set #", "Card Name", "Rarity", "Qty", "Condition", "Your Cost", "Notes"])
    for c in set_cards(sid):
        rec = coll.get(c["n"]) or {}
        paid = sum(b.get("price") or 0 for b in rec.get("purchases") or [] if isinstance(b, dict))
        w.writerow([c["n"], c["name"], c.get("rarity", ""), int(rec.get("qty") or 0), rec.get("cond") or "",
                    f"{paid:.2f}" if paid else "", rec.get("note") or ""])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")   # the mark helps Excel read accents like Pokémon


def apply_import(sid, plan):
    """Make the changes from import_plan. Saves a backup first. Returns the backup's file name."""
    if not plan["changes"]:
        return ""
    name = auto_backup("before-import")
    with lock:
        coll = read_json(sdir(sid, "collection.json"), {})
        for ch in plan["changes"]:
            rec = coll.get(ch["n"]) or {}
            buys = [b for b in (rec.get("purchases") or []) if isinstance(b, dict)]
            for _ in range(ch["add"]):
                buys.append({"d": "", "price": ch.get("each"), "where": ""})
            rec["purchases"] = buys
            rec["qty"] = len(buys)
            if ch.get("cond"):
                rec["cond"] = ch["cond"]
            if ch.get("note"):
                rec["note"] = ch["note"]
            coll[ch["n"]] = rec
        write_json(sdir(sid, "collection.json"), coll)
    log(f"{sid}: imported a spreadsheet ({len(plan['changes'])} cards changed)")
    return name


# ---------- backup and restore ----------

BACKUPS = os.path.join(APP, "backups")          # safety copies made before a restore, update or import (on your server only)
AUTO_KEEP = {"before-update": 10, "before-import": 5, "before-restore": 5}
AUTO_NAME_RE = re.compile(r"(before-(?:update|import|restore))-\d{8}-\d{6}(?:-\d{3})?\.zip")
MAX_RESTORE = 500 * 1024 * 1024
SET_FILES = ("collection", "prices", "history", "tcg_ids", "slots", "shop", "pc_urls", "tcgdex_ids", "custom", "cards")
BACKUP_RE = re.compile(rf"(settings\.json|sets\.json|shows\.json|favicon|favicon\.json|sets/{SID_RE}/(?:{'|'.join(SET_FILES)})\.json"
                       rf"|sets/{SID_RE}/photos/{NUM_RE}(?:_back)?(?:\.json)?)")


def backup_names():
    """Every file a backup holds: your collection, prices, history, settings and photos.
    Card images and the set catalog are left out because they download again by themselves."""
    out = []
    for name in ("settings.json", "sets.json", "shows.json", "favicon", "favicon.json"):
        if os.path.isfile(os.path.join(DATA, name)):
            out.append(name)
    sets_root = os.path.join(DATA, "sets")
    for sid in sorted(os.listdir(sets_root)) if os.path.isdir(sets_root) else []:
        for f in SET_FILES:
            if os.path.isfile(sdir(sid, f + ".json")):
                out.append(f"sets/{sid}/{f}.json")
        pdir = sdir(sid, "photos")
        for f in sorted(os.listdir(pdir)) if os.path.isdir(pdir) else []:
            out.append(f"sets/{sid}/photos/{f}")
    return [n for n in out if BACKUP_RE.fullmatch(n)]


def make_backup(target):
    with lock:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("backup.json", json.dumps({"app": "pokemon-binder", "version": APP_VERSION, "created": now_iso()}))
            for name in backup_names():
                z.write(os.path.join(DATA, name), name)


def auto_backup(kind):
    """Save a backup of all binder data in backups/ on BEN before something that changes it a lot
    (an update, a spreadsheet import, a restore). Keeps the newest few of each kind. Returns the file name."""
    os.makedirs(BACKUPS, exist_ok=True)
    name = f"{kind}-{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}.zip"
    tmp = os.path.join(BACKUPS, name + ".tmp")
    try:
        make_backup(tmp)
        os.replace(tmp, os.path.join(BACKUPS, name))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    old = sorted(f for f in os.listdir(BACKUPS) if f.startswith(kind + "-") and f.endswith(".zip"))
    for f in old[:-AUTO_KEEP.get(kind, 5)]:
        os.remove(os.path.join(BACKUPS, f))
    log(f"Saved a backup before {kind[7:]}: backups/{name}")
    return name


def list_auto_backups():
    """Backups saved on BEN, newest first: [{name, kind, created, size}]."""
    out = []
    for f in os.listdir(BACKUPS) if os.path.isdir(BACKUPS) else []:
        m = AUTO_NAME_RE.fullmatch(f)
        if m:
            path = os.path.join(BACKUPS, f)
            out.append({"name": f, "kind": m.group(1)[7:], "size": os.path.getsize(path),
                        "created": datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    return sorted(out, key=lambda x: x["created"] + x["name"], reverse=True)


def restore_backup(path):
    """Replace the binder's data with a backup file. Saves a safety copy of the current data first."""
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ValueError("That isn't a binder backup file")
    with z:
        names = [n for n in z.namelist() if BACKUP_RE.fullmatch(n)]
        if "sets.json" not in names or "backup.json" not in z.namelist():
            raise ValueError("That file doesn't look like a binder backup")
        try:
            sl = json.loads(z.read("sets.json"))
            assert isinstance(sl.get("order"), list) and isinstance(sl.get("meta"), dict)
            assert all(isinstance(x, str) and re.fullmatch(SID_RE, x) for x in sl["order"])
        except Exception:
            raise ValueError("The backup's set list is damaged")
        for n in names:
            if n.endswith(".json"):
                try:
                    json.loads(z.read(n))
                except Exception:
                    raise ValueError(f"The backup is damaged ({n} can't be read)")
        safety = auto_backup("before-restore")
        with lock:
            for sid in {n.split("/")[1] for n in names if n.startswith("sets/")}:
                shutil.rmtree(sdir(sid, "photos"), ignore_errors=True)
            if "favicon" not in names:
                for f in ("favicon", "favicon.json"):
                    if os.path.exists(os.path.join(DATA, f)):
                        os.remove(os.path.join(DATA, f))
            for n in names:
                dest = os.path.join(DATA, *n.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(n) as src, open(dest + ".tmp", "wb") as out:
                    shutil.copyfileobj(src, out)
                os.replace(dest + ".tmp", dest)
    log(f"Restored a backup ({len(names)} files). Safety copy of the old data: backups/{safety}")
    threading.Thread(target=warm_up, daemon=True).start()
    return len(names), safety


def warm_up():
    """Fetch card lists and images for every set in the binder (runs in the background)."""
    for sid in list(sets_list()["order"]):
        try:
            migrate_purchases(sid)
            if not os.path.exists(sdir(sid, "history.json")):
                with lock:
                    snapshot_history(sid)
        except Exception as e:
            log(f"{sid}: history setup: {e}")
        try:
            set_cards(sid)
            start_images(sid)
            if is_dex(sid):
                fetch_sprite(sid)
        except Exception as e:
            log(f"{sid}: couldn't load card list yet: {e}")
    catalog()
    start_dex_index()


# ---------- web ----------

# Which web addresses the binder answers to. IP addresses, localhost, one-word names (like "ben") and
# home/Tailscale names always work. Add others, like a reverse proxy name, in BINDER_HOSTS (comma separated).
# This blocks "DNS rebinding", where an outside website points its own name at your binder.
EXTRA_HOSTS = {h.strip().lower() for h in os.environ.get("BINDER_HOSTS", "").split(",") if h.strip()}
LOCAL_SUFFIXES = (".local", ".lan", ".home", ".home.arpa", ".internal", ".ts.net")


def host_ok(host_header):
    h = (host_header or "").strip().lower()
    if h.startswith("["):                       # IPv6 like [::1]:8765
        return True
    name = h.rsplit(":", 1)[0] if h.count(":") == 1 else h
    if not name or name in EXTRA_HOSTS or name == "localhost" or "." not in name:
        return True
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", name):
        return True
    return name.endswith(LOCAL_SUFFIXES)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send(self, code, body=b"", ctype="application/json", cache=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, ctype, cache="max-age=604800"):
        try:
            with open(path, "rb") as f:
                self.send(200, f.read(), ctype, cache)
        except OSError:
            self.send(404, b"not found", "text/plain")

    def body(self, limit):
        size = int(self.headers.get("Content-Length") or 0)
        if size <= 0 or size > limit:
            return None
        return self.rfile.read(size)

    def blocked(self, change):
        """Refuse requests sent to an unfamiliar address, and changes sent by another website.
        Browsers say where a request came from (Origin / Sec-Fetch-Site); changes must come from the binder's own page."""
        if not host_ok(self.headers.get("Host")):
            self.send(403, {"error": "Open the binder by its IP address (or add this name to BINDER_HOSTS)."})
            return True
        if change:
            site = (self.headers.get("Sec-Fetch-Site") or "").lower()
            origin = self.headers.get("Origin")
            if site and site not in ("same-origin", "none"):
                log(f"Blocked a {self.command} to {self.path} from another website ({site}).")
                self.send(403, {"error": "Changes can only come from the binder's own page."})
                return True
            if origin and origin != "null" and urllib.parse.urlparse(origin).netloc.lower() != (self.headers.get("Host") or "").lower():
                log(f"Blocked a {self.command} to {self.path} from {origin}.")
                self.send(403, {"error": "Changes can only come from the binder's own page."})
                return True
            if origin == "null":
                self.send(403, {"error": "Changes can only come from the binder's own page."})
                return True
        return False

    def in_binder(self, sid):
        return sid in sets_list()["order"]

    def do_GET(self):
        if self.blocked(False):
            return
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self.send_file(os.path.join(APP, "index.html"), "text/html; charset=utf-8", "no-cache")
        if path in ("/favicon", "/favicon.ico"):
            if os.path.exists(ICON_FILE):
                return self.send_file(ICON_FILE, read_json(ICON_FILE + ".json", {}).get("type", "image/png"), "no-cache")
            return self.send(200, DEFAULT_ICON, "image/svg+xml", "no-cache")
        if path == "/api/icon":
            return self.send(200, {"custom": os.path.exists(ICON_FILE)}, cache="no-store")
        if path == "/api/backups":
            return self.send(200, {"backups": list_auto_backups()}, cache="no-store")
        m_tp = re.fullmatch(rf"/api/set/({SID_RE})/template\.csv", path)
        if m_tp:
            sid = m_tp.group(1)
            if not self.in_binder(sid) or is_dex(sid):
                return self.send(400, {"error": "Templates are for set binders"})
            body = import_template(sid)
            fname = re.sub(r"[^A-Za-z0-9]+", "-", sets_list()["meta"].get(sid, {}).get("name", sid)).strip("-") or sid
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="{fname}-binder-template.csv"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        m_bk = re.fullmatch(r"/api/backups/([A-Za-z0-9.\-]+)", path)
        if m_bk:
            name = m_bk.group(1)
            fp = os.path.join(BACKUPS, name)
            if not AUTO_NAME_RE.fullmatch(name) or not os.path.isfile(fp):
                return self.send(404, {"error": "That backup isn't on BEN any more"})
            with open(fp, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="pokemon-binder-{name}"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/backup":
            buf = io.BytesIO()
            try:
                make_backup(buf)
            except Exception as e:
                return self.send(500, {"error": f"Couldn't make the backup: {e}"})
            body = buf.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="pokemon-binder-backup-{time.strftime("%Y-%m-%d")}.zip"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/version":
            return self.send(200, version_info(), cache="no-store")
        if path == "/api/update/check":
            if not GH_REPO:
                return self.send(400, {"error": "Changelog needs GitHub updates"})
            try:
                return self.send(200, check_github(), cache="no-store")
            except Exception as e:
                update_status["error"] = gh_error(e)
                return self.send(502, {"error": update_status["error"]})
        if path == "/api/sets":
            sl = sets_list()
            out = []
            for sid in sl["order"]:
                m = dict(sl["meta"].get(sid, {"id": sid, "name": sid}))
                coll = read_json(sdir(sid, "collection.json"), {})
                m["owned"] = sum(1 for v in coll.values() if (v or {}).get("qty", 0) > 0)
                cards = read_json(sdir(sid, "cards.json"), None)
                m["custom"] = len(custom_list(sid))
                m["count"] = (len(cards) if cards is not None else m.get("total", 0)) + m["custom"]
                m["images"] = sid in img_jobs
                if cards is not None:
                    m["totals"] = set_totals(sid)
                out.append(m)
            return self.send(200, {"sets": out}, cache="no-store")
        if path == "/api/pokedex":
            idx = dex_index()
            if dex_stale(idx):
                start_dex_index()
            out = {"ready": bool(idx), "building": dex_job["running"], "done": dex_job["done"],
                   "total": dex_job["total"], "error": dex_job["error"], "list": []}
            if idx:
                out["list"] = sorted(({"dex": int(d), "name": nm, "count": len(idx["cards"].get(d, []))}
                                      for d, nm in (idx.get("names") or {}).items()), key=lambda x: x["dex"])
            return self.send(200, out, cache="no-store")
        if path == "/api/shows":
            st = shows_state()
            return self.send(200, {"shows": sorted((tidy_show(x) for x in st["shows"].values()), key=lambda s: (s["date"], s["name"])),
                                   "areas": st["areas"], "auto": st["auto"], "scanned": st.get("scanned", ""),
                                   "firstScan": st.get("firstScan", ""), "error": st.get("error", ""), "running": shows_job["running"],
                                   "done": shows_job["done"], "total": shows_job["total"],
                                   "today": today_local()}, cache="no-store")
        if path == "/api/changelog":
            return self.send(200, changelog(), cache="no-store")
        if path == "/api/progress":
            # everything BEN is working on, for the loading bars
            imgs = {sid: dict(v) for sid, v in list(img_jobs.items()) if isinstance(v, dict)}
            return self.send(200, {"prices": job, "images": imgs, "pokedex": dex_job, "shows": shows_job},
                             cache="no-store")
        if path == "/api/catalog":
            return self.send(200, {"sets": catalog()}, cache="no-store")
        if path == "/api/refresh":
            return self.send(200, job, cache="no-store")
        if path == "/api/settings":
            st = get_settings()
            out = {k: st[k] for k in ("auto", "time", "tz", "slots")}
            out["backup"] = bool(st.get("backup", True))
            out["options"] = {"raw": RAW_CONDS, "graders": GRADERS, "grades": GRADES}
            out["next"] = next_run(st).isoformat() if st["auto"] else ""
            out["lastAuto"] = st.get("lastAuto", "")
            return self.send(200, out, cache="no-store")
        if path == "/api/spending":
            try:
                return self.send(200, spending(), cache="no-store")
            except Exception as e:
                return self.send(500, {"error": f"Couldn't work out spending: {e}"})
        m = re.fullmatch(rf"/api/set/({SID_RE})/history", path)
        if m:
            return self.send(200, read_json(sdir(m.group(1), "history.json"), {}), cache="no-store")
        m = re.fullmatch(rf"/api/set/({SID_RE})/state", path)
        if m:
            sid = m.group(1)
            if not self.in_binder(sid):
                return self.send(404, {"error": "Set not in binder"})
            try:
                cards = set_cards(sid)
            except Exception as e:
                return self.send(502, {"error": f"Couldn't load the card list: {e}"})
            with lock:
                body = {"set": sets_list()["meta"].get(sid, {}), "cards": cards,
                        "collection": read_json(sdir(sid, "collection.json"), {}),
                        "prices": read_json(sdir(sid, "prices.json"), {}), "slots": set_slots(sid),
                        "shop": read_json(sdir(sid, "shop.json"), {})}
            return self.send(200, body, cache="no-store")
        m = re.fullmatch(rf"/set/({SID_RE})/sprite\.png", path)
        if m:
            return self.send_file(sdir(m.group(1), "sprite.png"), "image/png")
        m = re.fullmatch(rf"/set/({SID_RE})/img/({NUM_RE})\.png", path)
        if m:
            return self.send_file(image_path(m.group(1), m.group(2)), "image/png")
        m = re.fullmatch(rf"/set/({SID_RE})/photo/({NUM_RE})(?:/(back))?", path)
        if m:
            name = m.group(2) + ("_back" if m.group(3) else "")
            meta = read_json(sdir(m.group(1), "photos", name + ".json"), {})
            return self.send_file(sdir(m.group(1), "photos", name), meta.get("type", "image/jpeg"), "no-cache")
        self.send(404, b"not found", "text/plain")

    def do_PUT(self):
        if self.blocked(True):
            return
        if self.path == "/api/settings":
            return self.do_PUT_settings()
        if self.path == "/api/shows":
            return self.do_PUT_shows()
        m = re.fullmatch(rf"/api/set/({SID_RE})/slots", self.path)
        if m:
            return self.do_PUT_slots(m.group(1))
        m = re.fullmatch(rf"/api/set/({SID_RE})/custom/(c\d{{1,5}})", self.path)
        if m:
            if not self.in_binder(m.group(1)):
                return self.send(400, {"error": "That binder isn't here"})
            try:
                return self.send(200, save_custom(m.group(1), m.group(2), json.loads(self.body(8192) or b"{}")))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        m = re.fullmatch(rf"/api/set/({SID_RE})/shop", self.path)
        if m:
            return self.do_PUT_shop(m.group(1))
        m = re.fullmatch(rf"/api/set/({SID_RE})/card/({NUM_RE})", self.path)
        raw = self.body(64 * 1024) if m else None
        if not m or raw is None or not self.in_binder(m.group(1)):
            return self.send(400, {"error": "bad request"})
        try:
            rec = json.loads(raw)
            assert isinstance(rec, dict)
        except Exception:
            return self.send(400, {"error": "bad json"})
        sid, n = m.groups()
        with lock:
            coll = read_json(sdir(sid, "collection.json"), {})
            coll[n] = rec
            write_json(sdir(sid, "collection.json"), coll)
        self.send(200, {"ok": True})

    def do_PUT_shows(self):
        """Card show options: the towns to look in and whether to scan every week."""
        try:
            new = json.loads(self.body(4096) or b"{}")
            st = shows_state()
            if "auto" in new:
                st["auto"] = bool(new["auto"])
            if "areas" in new:
                areas = [str(a).strip() for a in new["areas"] if str(a).strip()]
                assert 1 <= len(areas) <= 40 and all(len(a) <= 40 and re.fullmatch(r"[A-Za-z .'\-]+", a) for a in areas)
                st["areas"] = list(dict.fromkeys(areas))
        except Exception:
            return self.send(400, {"error": "Use town names separated by commas, like Richmond, Midlothian"})
        with lock:
            write_json(SHOWS_FILE, st)
        return self.send(200, {"ok": True})

    def do_PUT_shop(self, sid):
        """Save the shopping list order: a sort mode, plus your own card order for "My order"."""
        if not self.in_binder(sid):
            return self.send(404, {"error": "Set not in binder"})
        try:
            new = json.loads(self.body(64 * 1024) or b"{}")
            mode = new.get("mode")
            order = new.get("order") or []
            assert mode in ("lo", "hi", "num", "mine")
            assert isinstance(order, list) and len(order) <= 1000
            assert all(isinstance(n, str) and re.fullmatch(NUM_RE, n) for n in order)
            upg = new.get("upg") or {"from": ["HP", "DMG"], "to": "LP"}
            assert isinstance(upg.get("from"), list) and all(c in RAW_CONDS for c in upg["from"]) and upg.get("to") in RAW_CONDS
        except Exception:
            return self.send(400, {"error": "Invalid shopping list order"})
        with lock:
            write_json(sdir(sid, "shop.json"), {"mode": mode, "order": list(dict.fromkeys(order)),
                                                "upg": {"from": list(dict.fromkeys(upg["from"])), "to": upg["to"]}})
        return self.send(200, {"ok": True})

    def do_PUT_slots(self, sid):
        """Save one binder's price options, then recalculate its prices from stored sales."""
        if not self.in_binder(sid):
            return self.send(404, {"error": "Set not in binder"})
        try:
            new = json.loads(self.body(4096) or b"{}")
            assert isinstance(new, dict)
        except Exception:
            return self.send(400, {"error": "Invalid price options"})
        try:
            slots = clean_slots(new.get("slots"))
        except ValueError as e:
            return self.send(400, {"error": str(e) or "Invalid price options"})
        except Exception:
            return self.send(400, {"error": "Invalid price options"})
        with lock:
            write_json(sdir(sid, "slots.json"), slots)
        return self.send(200, {"ok": True, "slots": slots, "needsRefresh": recompute_prices([sid])})

    def do_PUT_settings(self):
        raw = self.body(4096)
        try:
            new = json.loads(raw or b"{}")
            st = read_json(SETTINGS, {})
            if "auto" in new:
                st["auto"] = bool(new["auto"])
            if "time" in new:
                assert re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", new["time"])
                st["time"] = new["time"]
            if "tz" in new:
                assert re.fullmatch(r"[A-Za-z_]+(/[A-Za-z_+\-]+){0,2}", new["tz"])
                st["tz"] = new["tz"]
            if "offset" in new:
                st["offset"] = int(new["offset"])
            slots_changed = "slots" in new or "backup" in new
            if "slots" in new:
                st["slots"] = clean_slots(new["slots"])
            if "backup" in new:
                st["backup"] = bool(new["backup"])
            # a new time today shouldn't be skipped just because today's run already happened earlier
            if "time" in new:
                merged = dict(DEFAULT_SETTINGS); merged.update(st)
                now = local_now(merged)
                h, m = map(int, merged["time"].split(":"))
                if now < now.replace(hour=h, minute=m, second=0, microsecond=0):
                    st["lastAuto"] = ""
            with lock:
                write_json(SETTINGS, st)
        except Exception as e:
            return self.send(400, {"error": str(e) if isinstance(e, ValueError) and str(e) else "Invalid settings"})
        merged = get_settings()
        out = {"ok": True, "next": next_run(merged).isoformat() if merged["auto"] else ""}
        if slots_changed:
            out["needsRefresh"] = recompute_prices()
        return self.send(200, out)

    def do_DELETE(self):
        if self.blocked(True):
            return
        if self.path == "/api/icon":
            for f in (ICON_FILE, ICON_FILE + ".json"):
                if os.path.exists(f):
                    os.remove(f)
            return self.send(200, {"ok": True})
        m = re.fullmatch(rf"/api/set/({SID_RE})/custom/(c\d{{1,5}})", self.path)
        if m:
            if not self.in_binder(m.group(1)):
                return self.send(400, {"error": "That binder isn't here"})
            try:
                delete_custom(m.group(1), m.group(2))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            return self.send(200, {"ok": True})
        m = re.fullmatch(rf"/api/sets/({SID_RE})", self.path)
        if not m:
            return self.send(400, {"error": "bad request"})
        remove_set(m.group(1))
        self.send(200, {"ok": True})

    def do_POST(self):
        if self.blocked(True):
            return
        path = self.path.split("?")[0]
        if path == "/api/restore":
            size = int(self.headers.get("Content-Length") or 0)
            if size <= 0 or size > MAX_RESTORE:
                return self.send(413, {"error": "That file is empty or too big"})
            fd, tmp = tempfile.mkstemp(suffix=".zip", dir=APP)
            try:
                with os.fdopen(fd, "wb") as f:
                    left = size
                    while left:
                        chunk = self.rfile.read(min(left, 1 << 20))
                        if not chunk:
                            break
                        f.write(chunk)
                        left -= len(chunk)
                count, safety = restore_backup(tmp)
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            except Exception as e:
                return self.send(500, {"error": f"Restore failed: {e}"})
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            return self.send(200, {"ok": True, "files": count, "safety": safety})
        if path == "/api/backups/restore":
            raw = self.body(4096)
            try:
                name = json.loads(raw or b"{}").get("name", "")
                assert AUTO_NAME_RE.fullmatch(name) and os.path.isfile(os.path.join(BACKUPS, name))
            except Exception:
                return self.send(400, {"error": "That backup isn't on BEN any more"})
            try:
                count, safety = restore_backup(os.path.join(BACKUPS, name))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            except Exception as e:
                return self.send(500, {"error": f"Restore failed: {e}"})
            return self.send(200, {"ok": True, "files": count, "safety": safety})
        m_cu = re.fullmatch(rf"/api/set/({SID_RE})/custom", path)
        if m_cu:
            sid = m_cu.group(1)
            if not self.in_binder(sid):
                return self.send(400, {"error": "That binder isn't here"})
            try:
                return self.send(200, save_custom(sid, None, json.loads(self.body(8192) or b"{}")))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        m_imp = re.fullmatch(rf"/api/set/({SID_RE})/import", path)
        if m_imp:
            sid = m_imp.group(1)
            if not self.in_binder(sid):
                return self.send(400, {"error": "That binder isn't here"})
            raw = self.body(MAX_IMPORT)
            if not raw:
                return self.send(413, {"error": "That file is empty or too big (10 MB max)"})
            apply = "apply=1" in (self.path.split("?") + [""])[1]
            try:
                rows = read_sheet(raw)
                plan = import_plan(sid, rows)
                if apply:
                    plan["backup"] = apply_import(sid, plan)
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            except Exception as e:
                log(f"{sid}: import failed: {e}")
                return self.send(500, {"error": f"Import failed: {e}"})
            return self.send(200, plan)
        if path == "/api/icon":
            ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if ctype not in ICON_TYPES:
                return self.send(400, {"error": "Use a PNG, JPG, WebP, GIF or ICO image"})
            raw = self.body(MAX_ICON)
            if raw is None:
                return self.send(413, {"error": "That image is too big (2 MB max)"})
            with lock:
                with open(ICON_FILE, "wb") as f:
                    f.write(raw)
                write_json(ICON_FILE + ".json", {"type": ctype})
            return self.send(200, {"ok": True, "v": int(time.time())})
        if path == "/api/sets":
            raw = self.body(4096)
            try:
                sid = json.loads(raw or b"{}").get("id", "")
                assert re.fullmatch(SID_RE, sid)
                meta = add_set(sid)
            except urllib.error.URLError as e:
                return self.send(502, {"error": f"Couldn't download the card list: {e}"})
            except Exception as e:
                return self.send(400, {"error": str(e) or "Couldn't add that set"})
            return self.send(200, meta)
        if path == "/api/update":
            # install the latest version (from GitHub, or the updates folder)
            try:
                if GH_REPO:
                    installed = install_from_github()
                elif os.path.isdir(UPDATES):
                    installed = install_files(UPDATES, "update from the updates folder")
                else:
                    return self.send(400, {"error": "Updates aren't set up"})
            except Exception as e:
                return self.send(502, {"error": gh_error(e)})
            restarting = "server.py" in installed
            self.send(200, {"installed": installed, "restarting": restarting})
            if restarting:
                threading.Thread(target=restart_self, args=(1,), daemon=True).start()
            return
        if path == "/api/rollback":
            raw = self.body(4096)
            try:
                vid = json.loads(raw or b"{}").get("id", "")
                installed = rollback(vid)
            except Exception as e:
                return self.send(400, {"error": str(e) or "Couldn't roll back"})
            restarting = "server.py" in installed
            self.send(200, {"installed": installed, "restarting": restarting})
            if restarting:
                threading.Thread(target=restart_self, args=(1,), daemon=True).start()
            return
        if path == "/api/shows/scan":
            if not shows_job["running"]:
                threading.Thread(target=scan_shows, args=("manual",), daemon=True).start()
                time.sleep(0.2)
            return self.send(200, {"running": shows_job["running"]})
        if path == "/api/refresh":
            raw = self.body(4096)
            sid = json.loads(raw or b"{}").get("set", "") if raw else ""
            if not job["running"] and sid and self.in_binder(sid):
                threading.Thread(target=refresh_prices, args=(sid, "manual"), daemon=True).start()
                time.sleep(0.2)
            return self.send(200, job)
        m = re.fullmatch(rf"/api/set/({SID_RE})/photo/({NUM_RE})(?:/(back))?", path)
        ctype = self.headers.get("Content-Type", "")
        if not m or not ctype.startswith("image/") or not self.in_binder(m.group(1)):
            return self.send(400, {"error": "bad request"})
        raw = self.body(MAX_PHOTO)
        if raw is None:
            return self.send(413, {"error": "too large"})
        sid, n, back = m.groups()
        name = n + ("_back" if back else "")
        os.makedirs(sdir(sid, "photos"), exist_ok=True)
        with open(sdir(sid, "photos", name), "wb") as f:
            f.write(raw)
        write_json(sdir(sid, "photos", name + ".json"), {"type": ctype})
        self.send(200, {"v": int(time.time())})


def test_card(card_id):
    try:
        print(f"Card {card_id}: looking up the TCGplayer product (fresh, not the saved one)")
        pid = product_id(card_id, {}, verbose=True)
        print(f"Card {card_id}: TCGplayer product id = {pid}")
        if pid:
            test_tcgplayer(pid)
    except Exception as e:
        print(f"Card {card_id}: couldn't reach TCGplayer: {e}")
    sid, _, n = card_id.rpartition("-")
    card = next((c for c in set_cards(sid) if c["n"] == n), None)
    if not card:
        return
    print("Market prices (TCGdex):")
    try:
        tc = tcgdex_card(sid, card, {})
        usd = eur_to_usd()
        print(f"  Euro to dollar rate: {usd or 'not available, Cardmarket left out'}")
        mkt = tcgdex_market(tc, card.get("rarity", ""), usd) if tc else {}
        print(f"  Card: {tc.get('id') if tc else 'not found'}")
        if tc and not mkt:
            print("  No prices on this card")
        if mkt.get("tp"):
            print(f"  TCGplayer market ${mkt['tp']} ({mkt.get('tpVar')}), low ${mkt.get('tpLow')}, updated {mkt.get('tpUpd')}")
        if mkt.get("cm30") or mkt.get("cmTrend"):
            print(f"  Cardmarket 30-day avg ${mkt.get('cm30')}, trend ${mkt.get('cmTrend')} (converted from euros), updated {mkt.get('cmUpd')}")
    except Exception as e:
        print(f"  Couldn't reach TCGdex: {e}")
    print("Graded (PriceCharting sold listings, Unlimited only):")
    try:
        groups, url, _ = graded_for(sid, card, {})
    except Exception as e:
        print(f"  Couldn't reach PriceCharting: {e}")
        return
    print(f"  Page: {url or 'not found'}")
    if url and not groups:
        print("  No graded sales found on the page")
    for key in sorted((groups or {}), key=lambda k: (k.startswith("Any"), k)):
        a2, c2, d2 = groups[key]
        print(f"  {key:<8} ${a2}  from {c2} sale{'s' if c2 != 1 else ''}, latest {d2}")


def test_tcgplayer(pid):
    print("Sales by condition:")
    sales = condition_sales(pid, verbose=True)
    print(f"Sales collected: {len(sales)}")
    for s in [x for x in sales if is_match(x)][:10]:
        print(f"  {s.get('orderDate', '')[:10]}  {s.get('condition')}  {s.get('variant')}  ${s.get('purchasePrice')}")
    avg, count, last = lp_mp_average(sales)
    print(f"LP/MP Unlimited average: {avg} from {count} sales (latest {last})")
    print("By condition (Unlimited, TCGplayer):")
    for short, (a, c, d) in sorted(by_condition(sales).items(), key=lambda kv: list(COND_SHORT.values()).index(kv[0])):
        print(f"  {short:<4} ${a}  from {c} sale{'s' if c != 1 else ''}, latest {d}")


UPDATES = os.environ.get("BINDER_UPDATES", "/updates")
UPDATE_FILES = ("server.py", "index.html")
GH_REPO = os.environ.get("GITHUB_REPO", "g-i-n-g-y/pokemon-binder")
GH_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
VERSION_FILE = os.path.join(APP, ".version.json")   # {commit, subject, date, installed, paused}
PREVIOUS = os.path.join(APP, "previous")            # previous/<stamp>/{server.py, index.html, meta.json}
KEEP_VERSIONS = 3
update_status = {"source": "", "checked": "", "error": ""}


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def current_version():
    return read_json(VERSION_FILE, {})


def same_file(a, b):
    try:
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False


def file_version(path):
    """The APP_VERSION written in a server.py file, or "" for versions from before numbering."""
    try:
        with open(path) as f:
            m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', f.read(), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


def split_subject(subject):
    """'v1.2: Add photos' -> ('1.2', 'Add photos'); other subjects -> ('', subject)."""
    m = re.match(r"v(\d+(?:\.\d+)+)\s*[:\-]\s*(.*)", subject or "")
    return (m.group(1), m.group(2)) if m else ("", subject or "")


def server_ok(path):
    """True if the server.py at `path` has no syntax errors."""
    try:
        with open(path) as f:
            compile(f.read(), path, "exec")
        return True
    except SyntaxError as e:
        log(f"Update skipped: the new server.py has an error on line {e.lineno}. Still running the current version.")
        return False


def save_current_version():
    """Keep a copy of the running version so it can be rolled back to later (newest 3 are kept)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    dest = os.path.join(PREVIOUS, stamp)
    os.makedirs(dest, exist_ok=False)
    for name in UPDATE_FILES:
        if os.path.exists(os.path.join(APP, name)):
            shutil.copy2(os.path.join(APP, name), os.path.join(dest, name))
    cur = current_version()
    write_json(os.path.join(dest, "meta.json"), {"version": file_version(os.path.join(APP, "server.py")),
                                                  "commit": cur.get("commit", ""), "subject": cur.get("subject", ""),
                                                  "date": cur.get("date", ""), "installed": cur.get("installed", ""),
                                                  "saved": now_iso()})
    for old in list_versions()[KEEP_VERSIONS:]:
        shutil.rmtree(os.path.join(PREVIOUS, old["id"]), ignore_errors=True)


def list_versions():
    """Saved previous versions, newest first."""
    out = []
    if os.path.isdir(PREVIOUS):
        for d in sorted(os.listdir(PREVIOUS), reverse=True):
            meta = read_json(os.path.join(PREVIOUS, d, "meta.json"), None)
            if meta is not None and os.path.isfile(os.path.join(PREVIOUS, d, "server.py")):
                out.append(dict(meta, id=d))
    return out


def install_files(folder, label):
    """Install changed program files from `folder`. Saves the running version first. Returns files installed."""
    changed = [n for n in UPDATE_FILES
               if os.path.isfile(os.path.join(folder, n)) and not same_file(os.path.join(folder, n), os.path.join(APP, n))]
    if not changed:
        return []
    if "server.py" in changed and not server_ok(os.path.join(folder, "server.py")):
        return []   # skip the whole update so the page and server never end up mismatched
    try:
        auto_backup("before-update")
    except Exception as e:
        log(f"Update skipped: couldn't save a backup first ({e})")
        raise RuntimeError(f"Update skipped because a backup couldn't be saved first: {e}")
    save_current_version()
    for name in changed:
        dst = os.path.join(APP, name)
        shutil.copyfile(os.path.join(folder, name), dst + ".tmp")
        os.replace(dst + ".tmp", dst)
    log(f"Installed {label}: " + ", ".join(changed))
    return changed


def gh_get(path, accept):
    headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "pokemon-binder"}
    if GH_TOKEN:  # only for a private copy of the repository
        headers["Authorization"] = f"Bearer {GH_TOKEN}"
    req = urllib.request.Request(f"https://api.github.com/repos/{GH_REPO}/{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def gh_json(path):
    return json.loads(gh_get(path, "application/vnd.github+json"))


def gh_error(e):
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 404:
            return "Repository " + GH_REPO + " wasn't found. It may be private"
        if e.code in (403, 429) and not GH_TOKEN:
            return "GitHub's hourly limit for update checks was reached. Try again in an hour"
        if e.code == 401:
            return "GitHub key was rejected (it may have expired)"
        return f"GitHub error {e.code}"
    return f"Couldn't reach GitHub ({e.__class__.__name__})"


def commit_info(c):
    msg = (c.get("commit") or {}).get("message", "")
    ver, text = split_subject(msg.split("\n")[0][:160])
    return {"sha": c.get("sha", ""), "version": ver, "subject": text,
            "date": ((c.get("commit") or {}).get("committer") or {}).get("date", "")}


def check_github():
    """What's new on GitHub compared with what's installed: {latest, changes, upToDate}."""
    update_status.update(source="github", checked=now_iso(), error="")
    latest = commit_info(gh_json(f"commits/{GH_BRANCH}"))
    ver = current_version()
    cur = ver.get("commit", "")
    if cur and not ver.get("subject"):   # versions installed before changelogs existed: fill in the description
        try:
            info = commit_info(gh_json(f"commits/{cur}"))
            write_json(VERSION_FILE, dict(ver, subject=info["subject"], date=info["date"]))
            ver = current_version()
        except Exception:
            pass
    if cur == latest["sha"]:
        return {"upToDate": True, "latest": latest, "changes": []}
    running = file_version(os.path.join(APP, "server.py"))
    try:   # the version written in the latest server.py, which is what would actually be installed
        m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"',
                      gh_get(f"contents/server.py?ref={latest['sha']}", "application/vnd.github.raw").decode("utf-8", "ignore"), re.M)
        latest["fileVersion"] = m.group(1) if m else ""
    except Exception:
        latest["fileVersion"] = latest["version"]
    if running and latest["fileVersion"] == running:
        return {"upToDate": True, "latest": latest, "changes": []}   # only non-app changes (like the README)
    changes = []
    if cur:
        try:
            cmp = gh_json(f"compare/{cur}...{latest['sha']}")
            if cmp.get("status") in ("ahead", "diverged"):
                changes = [commit_info(c) for c in reversed(cmp.get("commits") or [])]
                changes = [c for c in changes if c["version"]][:15] or changes[:15]
        except Exception:
            changes = []
    if not changes:
        changes = [latest]
    return {"upToDate": False, "latest": latest, "running": running, "changes": changes}


CHANGELOG_CACHE = {"at": 0, "text": "", "error": ""}


def ver_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


def parse_changelog(text):
    """CHANGELOG.md -> [{"v": "2.12", "date": "October 11, 2026", "items": [{"t": text, "sub": [..]}], "notes": [..]}]"""
    entries, cur = [], None
    for line in text.splitlines():
        m = re.match(r"##\s+v(\d+(?:\.\d+)+)\s*(?:\((.*?)\))?\s*$", line)
        if m:
            cur = {"v": m.group(1), "date": m.group(2) or "", "items": [], "notes": []}
            entries.append(cur)
            continue
        if cur is None or not line.strip():
            continue
        m = re.match(r"(\s*)[-*]\s+(.*)", line)
        if m:
            if len(m.group(1)) >= 2 and cur["items"]:
                cur["items"][-1]["sub"].append(m.group(2).strip())
            else:
                cur["items"].append({"t": m.group(2).strip(), "sub": []})
        else:
            cur["notes"].append(line.strip())
    return entries


def changelog():
    """Release notes from GitHub (checked at most once an hour), plus whether a newer version is out."""
    if GH_REPO and time.time() - CHANGELOG_CACHE["at"] > 3600:
        try:
            CHANGELOG_CACHE["text"] = gh_get(f"contents/CHANGELOG.md?ref={GH_BRANCH}", "application/vnd.github.raw").decode("utf-8", "ignore")
            CHANGELOG_CACHE["error"] = ""
        except Exception as e:
            CHANGELOG_CACHE["error"] = gh_error(e)
        CHANGELOG_CACHE["at"] = time.time()
    entries = parse_changelog(CHANGELOG_CACHE["text"])
    latest = entries[0]["v"] if entries else ""
    return {"running": APP_VERSION, "latest": latest, "entries": entries[:40],
            "updateAvailable": bool(latest) and ver_tuple(latest) > ver_tuple(APP_VERSION),
            "repo": GH_REPO, "branch": GH_BRANCH, "error": CHANGELOG_CACHE["error"]}


def install_from_github(sha=None):
    """Download server.py and index.html at `sha` (default: latest) and install them. Returns files installed."""
    update_status.update(source="github", checked=now_iso(), error="")
    info = commit_info(gh_json(f"commits/{sha or GH_BRANCH}"))
    stage = os.path.join(APP, ".incoming")
    os.makedirs(stage, exist_ok=True)
    for name in UPDATE_FILES:
        with open(os.path.join(stage, name), "wb") as f:
            f.write(gh_get(f"contents/{name}?ref={info['sha']}", "application/vnd.github.raw"))
    installed = install_files(stage, f"update {info['sha'][:7]} ({info['subject']})")
    # record the version only if its server.py is what's now running
    if same_file(os.path.join(stage, "server.py"), os.path.join(APP, "server.py")):
        write_json(VERSION_FILE, dict(info, commit=info["sha"], installed=now_iso(), paused=False))
    return installed


def rollback(version_id):
    """Reinstall a saved previous version. Pauses automatic updates. Returns files installed."""
    folder = os.path.join(PREVIOUS, version_id)
    meta = read_json(os.path.join(folder, "meta.json"), None)
    if meta is None or not re.fullmatch(r"[0-9-]+", version_id):
        raise ValueError("That version isn't available")
    installed = install_files(folder, f"rollback to {meta.get('commit', '')[:7] or 'older version'}")
    if installed or same_file(os.path.join(folder, "server.py"), os.path.join(APP, "server.py")):
        write_json(VERSION_FILE, {"version": meta.get("version", ""), "commit": meta.get("commit", ""), "subject": meta.get("subject", ""),
                                  "date": meta.get("date", ""), "installed": now_iso(), "paused": True})
        shutil.rmtree(folder, ignore_errors=True)   # it's the running version now
    return installed


# Updates are never installed by themselves (not on start, not on a schedule).
# The only way in is Settings -> About -> Check for updates, which shows the changes and asks first.


def restart_self(delay=0):
    if delay:
        time.sleep(delay)
    log("Restarting with the new server.py...")
    os.execv(sys.executable, [sys.executable, "-u", os.path.abspath(__file__)])


def version_info():
    out = {}
    for name in UPDATE_FILES:
        try:
            out[name] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(os.path.join(APP, name))))
        except OSError:
            out[name] = ""
    cur = current_version()
    out.update(version=file_version(os.path.join(APP, "server.py")),
               updatesFolder=os.path.isdir(UPDATES), github=bool(GH_REPO), repo=GH_REPO,
               commit=cur.get("commit", ""), subject=cur.get("subject", ""), date=cur.get("date", ""),
               installed=cur.get("installed", ""), paused=bool(cur.get("paused")),
               previous=list_versions(), **{k: update_status[k] for k in ("source", "checked", "error")})
    return out


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--test":
        test_card(sys.argv[2] if "-" in sys.argv[2] else f"neo4-{sys.argv[2]}")
        sys.exit(0)
    setup()
    threading.Thread(target=warm_up, daemon=True).start()
    threading.Thread(target=scheduler, daemon=True).start()
    log("Pokemon Binder running on port 8080")
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
