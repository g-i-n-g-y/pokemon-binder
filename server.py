"""Pokemon Binder - tiny self-hosted collection tracker for BEN.

- Any number of English sets, each in data/sets/<set id>/
- Card lists come from the PokemonTCG/pokemon-tcg-data project on GitHub
- Card images are downloaded to BEN when a set is added
- Prices refresh once a day from TCGplayer recent sales (Unlimited, English, LP/MP)
Python standard library only. Listens on port 8080 inside the container.

Test one card's price lookup:  docker exec neo-binder python server.py --test neo4-107

Updates: the latest server.py and index.html are downloaded from the public GitHub
repository (GITHUB_REPO, default g-i-n-g-y/pokemon-binder) on every start and from the
"Check for updates" button. No key is needed. Set GITHUB_REPO to an empty value to turn
this off and use a folder mounted at /updates instead. GITHUB_TOKEN is optional and only
needed for a private copy of the repository. Replaced files are kept in previous/.
"""
import io, json, os, re, shutil, sys, tempfile, threading, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
try:
    from zoneinfo import ZoneInfo
except ImportError:  # very old Python
    ZoneInfo = None

APP_VERSION = "2.0"   # bump for every app update: 1.0 -> 1.1 for features/fixes, 2.0 for big changes

APP = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(APP, "data")
SETS_DIR = os.path.join(DATA, "sets")
SETS_FILE = os.path.join(DATA, "sets.json")
SETTINGS = os.path.join(DATA, "settings.json")
DEFAULT_SLOTS = [{"t": "raw", "c": "LP"}, {"t": "raw", "c": "MP"}]
DEFAULT_SETTINGS = {"auto": True, "time": "03:00", "tz": "America/New_York", "offset": -240, "lastAuto": "",
                    "slots": DEFAULT_SLOTS}
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
NUM_RE = r"[A-Za-z0-9\-]{1,12}"

lock = threading.Lock()
job_lock = threading.Lock()
job = {"running": False, "set": "", "name": "", "done": 0, "total": 0, "priced": 0, "message": ""}
img_jobs = {}


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
    cards = read_json(sdir(sid, "cards.json"), None)
    if cards is None:
        cards = fetch_cards(sid)
    return cards


def sets_list():
    return read_json(SETS_FILE, {"order": [], "meta": {}})


def add_set(sid):
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
        ok = 0
        for c in missing:
            ok += fetch_image(sid, c)
            time.sleep(0.2)
        log(f"{sid}: card images {ok} of {len(missing)} downloaded.")
    finally:
        img_jobs.pop(sid, None)


def start_images(sid):
    if sid in img_jobs:
        return
    img_jobs[sid] = True
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


def main_price(info_n, slots):
    """The price used in the grid and totals. Both slots raw: their combined average. Otherwise slot 1,
    falling back to slot 2. Returns (price, count, latest, source) or None."""
    vals = [(sl, slot_value(info_n, sl)) for sl in slots if sl["t"] != "none"]
    if all(sl["t"] == "raw" for sl, _ in vals):
        got = [v for _, v in vals if v]
        if not got:
            return None
        cnt = sum(v[1] for v in got)
        return (round(sum(v[0] * v[1] for v in got) / cnt, 2), cnt, max(v[2] or "" for v in got), "tcgplayer")
    for sl, v in vals:
        if v:
            return (v[0], v[1], v[2], "pricecharting" if sl["t"] == "graded" else "tcgplayer")
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
    for sid in (sids or list(sets_list()["order"])):
        slots = set_slots(sid)
        with lock:
            prices = read_json(sdir(sid, "prices.json"), {})
            p, info = prices.setdefault("p", {}), prices.get("info") or {}
            for n, inf in info.items():
                if wants_graded(slots) and "graded" not in inf:
                    missing = True
                mp = main_price(inf, slots)
                if mp:
                    p[n] = [mp[0]]
                    inf.update(count=mp[1], last=mp[2], src=mp[3])
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


def pc_is_card(html, card):
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    title = (m.group(1) if m else "").lower()
    return re.search(rf"#\s*{re.escape(card['n'].lower())}(?![0-9a-z])", title) is not None


def pc_url(sid, card, cache):
    """The PriceCharting page for this card (Unlimited), found once and remembered."""
    key = card["n"]
    if key in cache:
        return cache[key]
    set_name = sets_list()["meta"].get(sid, {}).get("name", sid)
    tries = [f"{PC}/game/pokemon-{slugify(set_name)}/{slugify(card['name'])}-{slugify(card['n'])}",
             f"{PC}/game/pokemon-{slugify(set_name)}-set/{slugify(card['name'])}-{slugify(card['n'])}"]
    for url in tries:
        try:
            final, html = pc_get(url)
            if "/game/" in final and pc_is_card(html, card):
                cache[key] = final
                return final
        except urllib.error.HTTPError:
            pass
    # fall back to PriceCharting's own search
    q = urllib.parse.quote_plus(f"pokemon {set_name} {card['name']} {card['n']}")
    final, html = pc_get(f"{PC}/search-products?type=prices&q={q}")
    if "/game/" in final and pc_is_card(html, card):
        cache[key] = final
        return final
    for path in re.findall(r'href="(/game/pokemon-[^"/]+/[^"#?]+)"', html):
        if "1st-edition" in path or "japanese" in path:
            continue
        if path.endswith("-" + slugify(card["n"])):
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
                pid = product_id(f"{sid}-{n}", ids)
                if pid:
                    sales = condition_sales(pid)
                    inf["cond"] = by_condition(sales)
                    inf["recent"] = recent_by_condition(sales)
                else:
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
            mp = main_price(inf, slots)
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


# ---------- totals per set (for the all-binders summary) ----------

def set_totals(sid):
    """Same math as the page header: value counts owned copies at their condition's price when set."""
    coll = read_json(sdir(sid, "collection.json"), {})
    cards = read_json(sdir(sid, "cards.json"), None) or []
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


# ---------- backup and restore ----------

BACKUPS = os.path.join(APP, "backups")          # safety copies made before a restore (on your server only)
MAX_RESTORE = 500 * 1024 * 1024
SET_FILES = ("collection", "prices", "history", "tcg_ids", "slots", "shop", "pc_urls", "cards")
BACKUP_RE = re.compile(rf"(settings\.json|sets\.json|favicon|favicon\.json|sets/{SID_RE}/(?:{'|'.join(SET_FILES)})\.json"
                       rf"|sets/{SID_RE}/photos/{NUM_RE}(?:_back)?(?:\.json)?)")


def backup_names():
    """Every file a backup holds: your collection, prices, history, settings and photos.
    Card images and the set catalog are left out because they download again by themselves."""
    out = []
    for name in ("settings.json", "sets.json", "favicon", "favicon.json"):
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
        os.makedirs(BACKUPS, exist_ok=True)
        safety = os.path.join(BACKUPS, time.strftime("before-restore-%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}.zip")
        make_backup(safety)
        old = sorted(f for f in os.listdir(BACKUPS) if f.startswith("before-restore-"))
        for f in old[:-5]:
            os.remove(os.path.join(BACKUPS, f))
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
    log(f"Restored a backup ({len(names)} files). Safety copy of the old data: {safety}")
    threading.Thread(target=warm_up, daemon=True).start()
    return len(names), os.path.basename(safety)


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
        except Exception as e:
            log(f"{sid}: couldn't load card list yet: {e}")
    catalog()


# ---------- web ----------

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

    def in_binder(self, sid):
        return sid in sets_list()["order"]

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self.send_file(os.path.join(APP, "index.html"), "text/html; charset=utf-8", "no-cache")
        if path in ("/favicon", "/favicon.ico"):
            if os.path.exists(ICON_FILE):
                return self.send_file(ICON_FILE, read_json(ICON_FILE + ".json", {}).get("type", "image/png"), "no-cache")
            return self.send(200, DEFAULT_ICON, "image/svg+xml", "no-cache")
        if path == "/api/icon":
            return self.send(200, {"custom": os.path.exists(ICON_FILE)}, cache="no-store")
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
                m["count"] = len(cards) if cards is not None else m.get("total", 0)
                m["images"] = sid in img_jobs
                if cards is not None:
                    m["totals"] = set_totals(sid)
                out.append(m)
            return self.send(200, {"sets": out}, cache="no-store")
        if path == "/api/catalog":
            return self.send(200, {"sets": catalog()}, cache="no-store")
        if path == "/api/refresh":
            return self.send(200, job, cache="no-store")
        if path == "/api/settings":
            st = get_settings()
            out = {k: st[k] for k in ("auto", "time", "tz", "slots")}
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
        if self.path == "/api/settings":
            return self.do_PUT_settings()
        m = re.fullmatch(rf"/api/set/({SID_RE})/slots", self.path)
        if m:
            return self.do_PUT_slots(m.group(1))
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
            slots_changed = "slots" in new
            if slots_changed:
                st["slots"] = clean_slots(new["slots"])
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
        if self.path == "/api/icon":
            for f in (ICON_FILE, ICON_FILE + ".json"):
                if os.path.exists(f):
                    os.remove(f)
            return self.send(200, {"ok": True})
        m = re.fullmatch(rf"/api/sets/({SID_RE})", self.path)
        if not m:
            return self.send(400, {"error": "bad request"})
        remove_set(m.group(1))
        self.send(200, {"ok": True})

    def do_POST(self):
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


def apply_updates():
    """Run on start. Returns True if server.py changed (the server then restarts itself)."""
    if GH_REPO:
        if current_version().get("paused"):
            log("Automatic updates are paused after a rollback. Use Check for updates to install the latest.")
            return False
        try:
            return "server.py" in install_from_github()
        except Exception as e:
            update_status["error"] = gh_error(e)
            log(f"Update check: {update_status['error']}")
            return False
    if os.path.isdir(UPDATES):
        update_status.update(source="folder", checked=now_iso(), error="")
        return "server.py" in install_files(UPDATES, "update from the updates folder")
    return False


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
    if apply_updates():
        restart_self()
    setup()
    threading.Thread(target=warm_up, daemon=True).start()
    threading.Thread(target=scheduler, daemon=True).start()
    log("Pokemon Binder running on port 8080")
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
