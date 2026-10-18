"""Pokemon Binder - tiny self-hosted collection tracker you run on your own server.

- Any number of English sets, each in data/sets/<set id>/
- Card lists come from the PokemonTCG/pokemon-tcg-data project on GitHub
- Card images are downloaded to the server when a set is added
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
import ast, contextlib, gzip, io, json, os, unicodedata, re, shutil, socket, sqlite3, subprocess, sys, tempfile, threading, time, traceback, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
try:
    from zoneinfo import ZoneInfo
except ImportError:  # very old Python
    ZoneInfo = None

APP_VERSION = "3.21"   # 3.0 big changes, 2.12 features, 2.11.1 small fixes (see CHANGELOG.md)

APP = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(APP, "data")
SETS_DIR = os.path.join(DATA, "sets")
SETS_FILE = os.path.join(DATA, "sets.json")
SETTINGS = os.path.join(DATA, "settings.json")
DEFAULT_SLOTS = [{"t": "raw", "c": "LP"}, {"t": "raw", "c": "MP"}]
DEFAULT_SETTINGS = {"auto": True, "time": "03:00", "tz": "America/New_York", "offset": -240, "lastAuto": "",
                    "slots": DEFAULT_SLOTS, "backup": True, "serverName": "", "refreshAll": False}
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
# Card photo types. SVG is left out on purpose: an SVG file can carry a script.
PHOTO_TYPES = ("image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif", "image/avif")
# BINDER_PORT and BINDER_TRIAL are only used by the update check, which test-starts a new version on a spare port.
PORT = int(os.environ.get("BINDER_PORT") or 8080)
TRIAL = os.environ.get("BINDER_TRIAL") == "1"
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
CARD_INDEX = os.path.join(DATA, "card_index.json")   # every English card, for Find a card (made with the Pokémon list)
CARD_INDEX_V = 1   # bump when the every-card list gets new fields, so it's made again
OWN_RE = re.compile(r"my-(\d{1,5})")   # a binder you fill yourself, like my-1
SPRITES = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"

lock = threading.Lock()
job_lock = threading.Lock()
job = {"running": False, "set": "", "name": "", "done": 0, "total": 0, "priced": 0, "message": ""}
big = {"what": ""}   # an update, rollback or restore in progress (guarded by job_lock)


class Busy(Exception):
    """Another big job (price check, update, rollback, restore) is already running."""


@contextlib.contextmanager
def big_job(what):
    """One big job at a time: updates, rollbacks and restores never overlap each other or a price check.
    Set slot["keep"] = True inside to hold the slot until the binder restarts (after installing new program files)."""
    with job_lock:
        if job["running"]:
            raise Busy(f"A price check is running ({job['done']} of {job['total']} cards). Try again when it finishes")
        if big["what"]:
            raise Busy(f"{big['what'].capitalize()} is already in progress. Try again in a minute")
        big["what"] = what
    slot = {"keep": False}
    ok = False
    try:
        yield slot
        ok = True
    finally:
        if not (ok and slot["keep"]):
            with job_lock:
                big["what"] = ""
img_jobs = {}
dex_job = {"running": False, "done": 0, "total": 0, "error": ""}
shows_job = {"running": False, "error": "", "done": 0, "total": 0}


# ---------- small helpers ----------

LOG_TAIL = []   # the latest log lines, for Settings > About > Status


def log(msg):
    print(msg, flush=True)
    LOG_TAIL.append((time.time(), str(msg)))
    del LOG_TAIL[:-300]


def read_file_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_file_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


# ---------- storage: your data lives in one SQLite database, data/binder.db ----------
#
# Everything a backup holds (settings, binders, collection, prices, price history, shopping lists...) is kept in
# the database. Card pictures, your photos and downloaded lists (catalog, Pokédex index) stay as normal files.
# The rest of the program still calls read_json / write_json with the old file names (like
# data/sets/neo4/collection.json); those names are now just labels for what's in the database.
# Collection and prices get a row per card, and price history a row per day, so saving one card or one day
# only changes that row. One card's history can still be read on its own: json_extract(snap, '$."107"').
# Backups are still zips of the same JSON files, so backups work in both directions between old and new versions.

DB_FILE = os.path.join(DATA, "binder.db")
DB_SCHEMA = 1
SET_FILES = ("collection", "prices", "history", "tcg_ids", "slots", "shop", "pc_urls", "tcgdex_ids", "custom", "cards",
             "extra", "layout")
DOC_RE = re.compile(rf"(?:settings|sets|shows)\.json|sets/{SID_RE}/(?:{'|'.join(SET_FILES)})\.json")
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS docs (key TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS collection (sid TEXT NOT NULL, n TEXT NOT NULL, rec TEXT NOT NULL, PRIMARY KEY (sid, n));
CREATE TABLE IF NOT EXISTS prices (sid TEXT NOT NULL, n TEXT NOT NULL, p TEXT, info TEXT, PRIMARY KEY (sid, n));
CREATE TABLE IF NOT EXISTS history (sid TEXT NOT NULL, d TEXT NOT NULL, snap TEXT NOT NULL, PRIMARY KEY (sid, d));
"""
_MISSING = object()
db_lock = threading.RLock()   # one connection, shared; only one thread uses it at a time
_db = {"conn": None, "depth": 0, "retired": False}


def db():
    """The database connection (opened the first time it's needed). Call with db_lock held."""
    if _db["retired"]:
        raise RuntimeError("The binder is restarting into an older version")
    if _db["conn"] is None:
        os.makedirs(DATA, exist_ok=True)
        c = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None, timeout=30)
        c.execute("PRAGMA journal_mode=WAL")      # readers and the writer don't block each other; safe if the server loses power
        c.execute("PRAGMA synchronous=NORMAL")
        c.executescript(SCHEMA_SQL)
        _db["conn"] = c
    return _db["conn"]


@contextlib.contextmanager
def tx():
    """All-or-nothing changes: everything inside is saved together, or (on an error) none of it is."""
    with db_lock:
        c = db()
        if _db["depth"] == 0:
            c.execute("BEGIN IMMEDIATE")
        _db["depth"] += 1
        try:
            yield c
        except BaseException:
            _db["depth"] -= 1
            if _db["depth"] == 0:
                c.execute("ROLLBACK")
            raise
        _db["depth"] -= 1
        if _db["depth"] == 0:
            c.execute("COMMIT")


def doc_key(path):
    """'data/sets/neo4/collection.json' -> 'sets/neo4/collection.json' if it's kept in the database, else None."""
    rel = os.path.relpath(os.path.abspath(path), DATA).replace(os.sep, "/")
    return rel if DOC_RE.fullmatch(rel) else None


def _kind(key):
    """('neo4', 'collection') for 'sets/neo4/collection.json'; (None, None) for the top-level files."""
    parts = key[:-5].split("/")
    return (parts[1], parts[2]) if len(parts) == 3 else (None, None)


def _tabled_shape(kind, obj):
    """Collection, prices and history go in their own tables when they look normal; anything odd is kept whole."""
    if kind in ("collection", "history"):
        return isinstance(obj, dict) and (kind == "collection" or all(isinstance(v, dict) for v in obj.values()))
    if kind == "prices":
        return isinstance(obj, dict) and isinstance(obj.get("p", {}), dict) and isinstance(obj.get("info", {}), dict)
    return False


def _put_doc(c, key, body):
    c.execute("INSERT INTO docs (key, body) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET body = excluded.body",
              (key, json.dumps(body)))


def db_read(key):
    with db_lock:
        c = db()
        row = c.execute("SELECT body FROM docs WHERE key = ?", (key,)).fetchone()
        if row is None:
            return _MISSING
        body = json.loads(row[0])
        sid, kind = _kind(key)
        if kind not in ("collection", "prices", "history"):
            return body
        if "__raw" in body:
            return body["__raw"]
        if kind == "collection":
            return {n: json.loads(r) for n, r in c.execute("SELECT n, rec FROM collection WHERE sid = ? ORDER BY rowid", (sid,))}
        if kind == "prices":
            has = body.pop("__has", ["p", "info"])
            p, info = {}, {}
            for n, pv, iv in c.execute("SELECT n, p, info FROM prices WHERE sid = ? ORDER BY rowid", (sid,)):
                if pv is not None:
                    p[n] = json.loads(pv)
                if iv is not None:
                    info[n] = json.loads(iv)
            out = {}
            if "p" in has:
                out["p"] = p
            if "info" in has:
                out["info"] = info
            out.update(body)
            return out
        return {d: json.loads(snap) for d, snap in c.execute("SELECT d, snap FROM history WHERE sid = ? ORDER BY d", (sid,))}


def _sync_rows(c, table, sid, cols, rows):
    """Make `table` hold exactly `rows` for this set ({row key: values}), touching only rows that changed."""
    keys = ("d",) if table == "history" else ("n",)
    have = {r[:len(keys)]: r[len(keys):] for r in
            c.execute(f"SELECT {', '.join(keys + cols)} FROM {table} WHERE sid = ?", (sid,))}
    gone = [k for k in have if k not in rows]
    where = " AND ".join(f"{k} = ?" for k in keys)
    c.executemany(f"DELETE FROM {table} WHERE sid = ? AND {where}", [(sid,) + k for k in gone])
    sets = ", ".join(f"{col} = excluded.{col}" for col in cols)
    c.executemany(f"INSERT INTO {table} (sid, {', '.join(keys + cols)}) VALUES ({', '.join('?' * (1 + len(keys) + len(cols)))}) "
                  f"ON CONFLICT (sid, {', '.join(keys)}) DO UPDATE SET {sets}",
                  [(sid,) + k + v for k, v in rows.items() if have.get(k) != v])


def db_write(key, obj):
    sid, kind = _kind(key)
    with tx() as c:
        if kind in ("collection", "prices", "history"):
            if not _tabled_shape(kind, obj):
                for table in ("collection", "prices", "history"):
                    if table == kind:
                        c.execute(f"DELETE FROM {table} WHERE sid = ?", (sid,))
                return _put_doc(c, key, {"__raw": obj})
            if kind == "collection":
                _sync_rows(c, "collection", sid, ("rec",), {(str(n),): (json.dumps(v),) for n, v in obj.items()})
                return _put_doc(c, key, {})
            if kind == "prices":
                p, info = obj.get("p") or {}, obj.get("info") or {}
                rows = {}
                for n in list(p) + [n for n in info if n not in p]:
                    rows[(str(n),)] = (json.dumps(p[n]) if n in p else None, json.dumps(info[n]) if n in info else None)
                _sync_rows(c, "prices", sid, ("p", "info"), rows)
                body = {k: v for k, v in obj.items() if k not in ("p", "info")}
                body["__has"] = [k for k in ("p", "info") if k in obj]
                return _put_doc(c, key, body)
            _sync_rows(c, "history", sid, ("snap",), {(str(d),): (json.dumps(day),) for d, day in obj.items()})
            return _put_doc(c, key, {})
        _put_doc(c, key, obj)


def _tabled_ready(c, key):
    """True if this set's collection/history is stored as rows (so one row can be changed on its own)."""
    row = c.execute("SELECT body FROM docs WHERE key = ?", (key,)).fetchone()
    if row is None:
        _put_doc(c, key, {})
        return True
    return "__raw" not in json.loads(row[0])


def _owned(rec):
    return isinstance(rec, dict) and isinstance(rec.get("qty"), (int, float)) and rec["qty"] > 0


def collection_put(sid, n, rec):
    """Save one card's record (copies, purchases, condition...) without touching the rest of the binder.
    Also remembers the day a card first became owned ("got"), for Recently added on the home page."""
    key = f"sets/{sid}/collection.json"
    if _owned(rec) and not rec.get("got"):
        old = read_json(sdir(sid, "collection.json"), {}).get(n)
        rec = dict(rec, got=old["got"] if _owned(old) and old.get("got") else time.strftime("%Y-%m-%dT%H:%M"))
    elif not _owned(rec):
        rec = {k: v for k, v in rec.items() if k != "got"}
    with tx() as c:
        if not _tabled_ready(c, key):
            coll = db_read(key)
            coll = coll if isinstance(coll, dict) else {}
            coll[n] = rec
            return db_write(key, coll)
        c.execute("INSERT INTO collection (sid, n, rec) VALUES (?, ?, ?) ON CONFLICT (sid, n) DO UPDATE SET rec = excluded.rec",
                  (sid, n, json.dumps(rec)))


def history_put_day(sid, d, snap):
    """Save one day of prices ({card: price}), replacing that day only."""
    key = f"sets/{sid}/history.json"
    with tx() as c:
        if not _tabled_ready(c, key):
            hist = db_read(key)
            hist = hist if isinstance(hist, dict) else {}
            hist[d] = snap
            return db_write(key, hist)
        c.execute("INSERT INTO history (sid, d, snap) VALUES (?, ?, ?) ON CONFLICT (sid, d) DO UPDATE SET snap = excluded.snap",
                  (sid, d, json.dumps(snap)))


def read_json(path, default):
    key = doc_key(path)
    if key is None:
        return read_file_json(path, default)
    try:
        v = db_read(key)
    except sqlite3.Error as e:
        log(f"database: couldn't read {key}: {e}")
        return default
    return default if v is _MISSING else v


def write_json(path, obj):
    key = doc_key(path)
    if key is None:
        return write_file_json(path, obj)
    db_write(key, obj)


def data_exists(path):
    key = doc_key(path)
    if key is None:
        return os.path.exists(path)
    with db_lock:
        return db().execute("SELECT 1 FROM docs WHERE key = ?", (key,)).fetchone() is not None


def db_keys():
    with db_lock:
        return [k for (k,) in db().execute("SELECT key FROM docs ORDER BY key")]


def migrate_to_db():
    """First start on v3.0: copy your JSON files into the database, once. The old files are moved to
    data/pre-sqlite-<date>/ (not deleted), and backups made before the update still restore."""
    with db_lock:
        if db().execute("SELECT 1 FROM meta WHERE key = 'schema'").fetchone():
            return
    found = []
    for root, dirs, files in os.walk(DATA):
        dirs[:] = [d for d in dirs if d not in ("images", "photos") and not d.startswith("pre-sqlite")]
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), DATA).replace(os.sep, "/")
            if DOC_RE.fullmatch(rel):
                found.append(rel)
    skipped = []
    with tx() as c:
        for rel in sorted(found):
            try:
                with open(os.path.join(DATA, rel)) as f:
                    obj = json.load(f)
            except (OSError, ValueError) as e:
                skipped.append(rel)
                log(f"database: skipped {rel}, it couldn't be read ({e})")
                continue
            db_write(rel, obj)
        c.execute("INSERT INTO meta (key, value) VALUES ('schema', ?)", (str(DB_SCHEMA),))
        c.execute("INSERT INTO meta (key, value) VALUES ('created', ?)", (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),))
    if found:
        keep = os.path.join(DATA, "pre-sqlite-" + time.strftime("%Y%m%d-%H%M%S"))
        for rel in found:
            dest = os.path.join(keep, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                shutil.move(os.path.join(DATA, rel), dest)
            except OSError as e:
                log(f"database: couldn't move {rel} out of the way: {e}")
        log(f"Moved {len(found) - len(skipped)} data files into the database (data/binder.db). "
            f"The old files are in data/{os.path.basename(keep)}/")


def export_to_files():
    """Write everything in the database back out as the JSON files older versions read (used before a roll back)."""
    with db_lock:
        docs = [(k, db_read(k)) for k in db_keys()]
    for k, obj in docs:
        write_file_json(os.path.join(DATA, *k.split("/")), obj)
    return [k for k, _ in docs]


def retire_db():
    """After rolling back to a version without the database: set binder.db aside (renamed, not deleted)
    so that updating again later starts fresh from the files the older version kept."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    with db_lock:
        if _db["conn"] is not None:
            _db["conn"].close()
            _db["conn"] = None
        _db["retired"] = True
        for ext in ("", "-wal", "-shm"):
            if os.path.exists(DB_FILE + ext):
                os.replace(DB_FILE + ext, f"{DB_FILE}.rolled-back-{stamp}{ext}")


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
    """Every card in a binder: the card database's list, cards you added from Find a card, and custom cards."""
    cards = read_json(sdir(sid, "cards.json"), None)
    if cards is None:
        cards = [] if is_own(sid) else dex_cards(sid) if is_dex(sid) else fetch_cards(sid)
    return cards + extra_list(sid) + custom_cards(sid)


def binder_size(sid):
    """How many cards a binder holds, without downloading anything. None if its card list isn't saved yet."""
    cards = read_json(sdir(sid, "cards.json"), None)
    if cards is None and not is_own(sid):
        return None
    return len(cards or []) + len(extra_list(sid)) + len(custom_list(sid))


# ---------- cards added from Find a card ----------
# Saved per binder in extra.json, each remembering its own set, like the cards in a master set binder.
# Their number is the card database's id (like neo1-80), so it never clashes with a set's own numbers.
# Your own binders ("my-1") hold only these.

def extra_list(sid):
    out = read_json(sdir(sid, "extra.json"), [])
    return [c for c in out if isinstance(c, dict) and re.fullmatch(NUM_RE, str(c.get("n", "")))] if isinstance(out, list) else []


def forget_card(sid, n):
    """Delete everything saved for one card in a binder: copies, purchases, prices, history, photos, layout spot."""
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
    lay = read_json(sdir(sid, "layout.json"), None)
    if isinstance(lay, dict) and n in (lay.get("slots") or []):
        lay["slots"] = [None if x == n else x for x in lay["slots"]]
        write_json(sdir(sid, "layout.json"), lay)
    for f in (n, n + ".json", n + "_back", n + "_back.json"):
        if os.path.exists(sdir(sid, "photos", f)):
            os.remove(sdir(sid, "photos", f))
    for full in (True, False):
        if os.path.exists(image_path(sid, n, full)):
            os.remove(image_path(sid, n, full))


def add_card(sid, gid):
    """Put a card from the card database into a binder. Returns {"n": its number in this binder, "already": bool}."""
    card = index_card(gid)
    if not card:
        raise ValueError("That card isn't in the card list")
    with lock:
        if not is_multi(sid):
            local = gid[len(sid) + 1:] if gid.startswith(sid + "-") else None
            if local and any(c["n"] == local for c in (read_json(sdir(sid, "cards.json"), None) or [])):
                return {"n": local, "already": True}
        elif is_dex(sid) and any(c["n"] == gid for c in (read_json(sdir(sid, "cards.json"), None) or [])):
            return {"n": gid, "already": True}
        lst = extra_list(sid)
        if any(c["n"] == gid for c in lst):
            return {"n": gid, "already": True}
        if len(lst) >= 2000:
            raise ValueError("That's the most cards one binder can hold")
        lst.append(dict(card, extra=True, added=today_local()))
        write_json(sdir(sid, "extra.json"), lst)
    log(f"{sid}: added {gid} ({card['name']})")
    refresh_soon(sid, [gid])
    return {"n": gid, "already": False}


def remove_card(sid, n):
    """Take a card you added from Find a card back out of a binder."""
    with lock:
        lst = extra_list(sid)
        if not any(c["n"] == n for c in lst):
            raise ValueError("Only cards you added yourself can be taken out")
        write_json(sdir(sid, "extra.json"), [c for c in lst if c["n"] != n])
        forget_card(sid, n)


def refresh_soon(sid, ns):
    """Get prices for a few newly added cards in the background, once nothing else is checking prices."""
    if TRIAL:   # a test start answers pages only
        return

    def go():
        time.sleep(3)
        for _ in range(240):   # up to an hour
            if sid not in sets_list()["order"]:
                return
            have = {c["n"] for c in set_cards(sid)}
            left = [n for n in ns if n in have]
            if not left or refresh_prices(sid, "new card", only=set(left)) is not False:
                return
            time.sleep(15)
    threading.Thread(target=go, daemon=True).start()


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
        forget_card(sid, n)


def card_ref(sid, c):
    """(card id for price lookups, set name, number printed on the card).
    In a Pokémon master set binder each card remembers its own set."""
    if is_multi(sid) or c.get("custom") or c.get("extra"):
        return (None if c.get("custom") else c["n"]), c.get("set", ""), c.get("num", c["n"])
    return f"{sid}-{c['n']}", sets_list()["meta"].get(sid, {}).get("name", sid), c["n"]


# ---------- Pokémon master set binders ----------

def is_dex(sid):
    return bool(DEX_RE.fullmatch(sid or ""))


def is_own(sid):
    return bool(OWN_RE.fullmatch(sid or ""))


def is_multi(sid):
    """Binders whose cards come from many sets (master sets and your own binders)."""
    return is_dex(sid) or is_own(sid)


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
        by_dex, done_sets, every, set_info = {}, [], [], {}
        for i, st in enumerate(sets):
            dex_job["done"] = i
            try:
                raw = json.loads(http_get(f"{GH}/cards/en/{st['id']}.json"))
            except Exception as e:
                log(f"Pokémon list: {st['id']}: {e}")
                continue
            done_sets.append(st["id"])
            set_info[st["id"]] = [st["name"], st.get("series", ""), st.get("printedTotal", 0), st.get("releaseDate", ""),
                                  st.get("total", 0)]
            for c in raw:
                n = f"{st['id']}-{c['number']}"
                if not re.fullmatch(NUM_RE, n):
                    continue
                every.append([n, c["name"], str(c["number"]), c.get("rarity") or "", c.get("supertype", ""),
                              (c.get("images") or {}).get("large") or (c.get("images") or {}).get("small", ""), st["id"],
                              ((c.get("nationalPokedexNumbers") or [0])[0] or 0)])
                if c.get("supertype") != "Pokémon":
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
        write_json(DEX_INDEX, {"fetched": time.time(), "sets": done_sets, "names": names, "cards": by_dex, "cardIndex": CARD_INDEX_V})
        write_file_json(CARD_INDEX, {"fetched": time.time(), "sets": set_info, "cards": every})
        CARD_IDX["at"] = 0
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
    return (time.time() - idx.get("fetched", 0) > 30 * DAY or any(s["id"] not in have for s in catalog())
            or not os.path.isfile(CARD_INDEX) or idx.get("cardIndex") != CARD_INDEX_V)   # made before Find a card existed


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


# ---------- Find a card ----------
# Searches every English card (data/card_index.json, made with the Pokémon list). Only runs when you
# tap Search, never while typing.

CARD_IDX = {"at": 0, "cards": [], "sets": {}, "by": {}, "used": 0}
CARD_IDX_IDLE = 15 * 60   # the list takes about 20 MB in memory, so it's let go after 15 minutes without a search


def release_card_index():
    if CARD_IDX["at"] and time.time() - CARD_IDX["used"] > CARD_IDX_IDLE:
        CARD_IDX.update(at=0, cards=[], sets={}, by={})


def _fold(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t.replace("♀", " f").replace("♂", " m").replace("’", "'")


def _num_fold(t):
    t = _fold(t).strip().lstrip("#")
    m = re.fullmatch(r"([a-z]*)0*(\d+)([a-z]*)", t)
    return (m.group(1) + m.group(2) + m.group(3)) if m else t


def card_index():
    """The every-card list, kept in memory and reloaded when the file changes."""
    try:
        at = os.path.getmtime(CARD_INDEX)
    except OSError:
        return None
    CARD_IDX["used"] = time.time()
    if CARD_IDX["at"] != at:
        raw = read_file_json(CARD_INDEX, None)
        if not raw:
            return None
        sets = raw.get("sets") or {}
        cards = []
        for c in raw.get("cards") or []:
            st = sets.get(c[6]) or ["", "", 0, "", 0]
            cards.append((c, _fold(c[1]), _num_fold(c[2]), _fold(st[0]),
                          tuple(re.findall(r"[a-z0-9']+", _fold(c[1]))), tuple(re.findall(r"[a-z0-9']+", _fold(st[0])))))
        CARD_IDX.update(at=at, cards=cards, sets=sets, by={c[0][0]: c[0] for c in cards})
    return CARD_IDX


def _card_out(c, sets):
    st = sets.get(c[6]) or ["", "", 0, "", 0]
    return {"n": c[0], "name": c[1], "num": c[2], "rarity": c[3], "type": c[4], "img": c[5],
            "setId": c[6], "set": st[0], "pt": st[2], "date": st[3]}


def index_card(gid):
    """One card from the every-card list, shaped like a card in a master set binder."""
    idx = card_index()
    c = idx and idx["by"].get(gid)
    if not c:
        return None
    o = _card_out(c, idx["sets"])
    return {"n": o["n"], "num": o["num"], "set": o["set"], "pt": o["pt"], "date": o["date"], "name": o["name"],
            "rarity": o["rarity"], "type": o["type"], "img": o["img"], "src": o["setId"]}


def where_cards():
    """Which of your binders hold each card: {card id: [{sid, n, qty}]}."""
    out = {}
    for sid in sets_list()["order"]:
        coll = read_json(sdir(sid, "collection.json"), {})
        coll = coll if isinstance(coll, dict) else {}
        base = read_json(sdir(sid, "cards.json"), None) or []
        for c in base + extra_list(sid):
            gid = c["n"] if (is_multi(sid) or c.get("extra")) else f"{sid}-{c['n']}"
            rec = coll.get(c["n"]) if isinstance(coll.get(c["n"]), dict) else {}
            out.setdefault(gid, []).append({"sid": sid, "n": c["n"], "qty": int(rec.get("qty") or 0)})
    return out


def find_status():
    idx = card_index()
    if not idx and not dex_job["running"]:
        start_dex_index(force=True)
    return {"ready": bool(idx), "building": dex_job["running"], "done": dex_job["done"], "total": dex_job["total"],
            "error": dex_job["error"]}


def find(q):
    """Sets and cards matching what's typed: a name, the number printed on the card (80 or 80/111), a set, or a mix."""
    out = find_status()
    out.update(q=q, sets=[], cards=[], count=0)
    idx = card_index()
    if not idx:
        return out
    text = _fold(q)[:80]
    m = re.search(r"#?\s*([a-z]{0,6}\d{1,4}[a-z]?)\s*/\s*([a-z]{0,6}\d{1,4})", text)
    num = total = None
    if m:
        num, total = _num_fold(m.group(1)), _num_fold(m.group(2))
        text = text[:m.start()] + " " + text[m.end():]
    words = re.findall(r"[a-z0-9'.\-]+", text)
    if num is None:
        nums = [w for w in words if re.fullmatch(r"#?[a-z]{0,6}\d{1,4}[a-z]?", w) and any(ch.isdigit() for ch in w)
                and not re.fullmatch(r"(19|20)\d\d", w)]
        if nums:
            num = _num_fold(nums[-1])
            words.remove(nums[-1])
    words = [x for w in words for x in re.findall(r"[a-z0-9']+", w)]
    sets = idx["sets"]
    if words and num is None:
        phrase = " ".join(words)
        hits = []
        for sid, st in sets.items():
            name = _fold(st[0])
            if phrase in name or sid == phrase or all(w in name.split() or w in name for w in words):
                hits.append((0 if name == phrase or sid == phrase else 1, st[3], sid, st))
        hits.sort()
        mine = set(sets_list()["order"])
        out["sets"] = [{"id": sid, "name": st[0], "series": st[1], "pt": st[2], "date": st[3], "total": st[4],
                        "inBinder": sid in mine} for _, _, sid, st in hits[:12]]
    if not words and num is None:
        return out
    total_i = int(total) if total and total.isdigit() else None
    found = []
    for c, fname, fnum, fset, nwords, swords in idx["cards"]:
        if num is not None and fnum != num:
            continue
        st = sets.get(c[6]) or ["", "", 0, "", 0]
        if total is not None:
            if total_i is not None:
                if st[2] != total_i:
                    continue
            elif not fnum.startswith(re.sub(r"\d+", "", total)):
                continue
        in_name = 0
        ok = True
        for w in words:   # each typed word starts a word in the card's name or its set's name
            if any(x.startswith(w) for x in nwords):
                in_name += 1
            elif not any(x.startswith(w) for x in swords):
                ok = False
                break
        if not ok or (words and not in_name and num is None):
            continue
        score = (5 if num is not None else 0) + (5 if total is not None else 0) + in_name
        if words and fname == " ".join(words):
            score += 3
        found.append((-score, st[3], num_key(c[2]), c))
    found.sort(key=lambda x: x[:3])
    out["count"] = len(found)
    where = where_cards()
    for _, _, _, c in found[:60]:
        o = _card_out(c, sets)
        o["in"] = where.get(c[0], [])
        out["cards"].append(o)
    return out


def find_set(set_id):
    """Every card in one set, in number order, with which of your binders hold them."""
    out = find_status()
    idx = card_index()
    if not idx:
        return out
    st = idx["sets"].get(set_id)
    if not st:
        raise ValueError("That set isn't in the card list")
    where = where_cards()
    cards = sorted((t[0] for t in idx["cards"] if t[0][6] == set_id), key=lambda c: num_key(c[2]))
    out.update(set={"id": set_id, "name": st[0], "series": st[1], "pt": st[2], "date": st[3], "total": st[4],
                    "inBinder": set_id in sets_list()["order"]},
               cards=[dict(_card_out(c, idx["sets"]), **{"in": where.get(c[0], [])}) for c in cards])
    return out


# ---------- your own binders ----------

def add_own(name):
    """Start an empty binder you fill yourself from Find a card. Returns its details."""
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:40]
    if not name:
        raise ValueError("Give the binder a name")
    with lock:
        sl = sets_list()
        used = [int(m.group(1)) for m in (OWN_RE.fullmatch(k) for k in sl["meta"]) if m]
        sid = f"my-{max(used, default=0) + 1}"
        write_json(sdir(sid, "cards.json"), [])
        write_json(sdir(sid, "extra.json"), [])
        meta = {"id": sid, "name": name, "series": "My binder", "kind": "own", "printedTotal": 0, "total": 0,
                "releaseDate": "", "added": int(time.time())}
        sl["meta"][sid] = meta
        sl["order"].append(sid)
        write_json(SETS_FILE, sl)
    log(f"Added your own binder {name} ({sid})")
    return meta


def rename_own(sid, name):
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:40]
    if not name:
        raise ValueError("Give the binder a name")
    with lock:
        sl = sets_list()
        if not is_own(sid) or sid not in sl["meta"]:
            raise ValueError("Only your own binders can be renamed")
        sl["meta"][sid]["name"] = name
        write_json(SETS_FILE, sl)
    return sl["meta"][sid]


# ---------- binder layout (pages and pockets) ----------

POCKETS = (4, 9, 12, 16)
LAYOUT_ORDERS = ("num", "rarity", "dex", "type", "value", "owned", "added")


def save_layout(sid, raw):
    """Save how a binder's cards sit in its pages: pocket size, starting order and every slot (card or empty)."""
    try:
        pockets = int(raw.get("pockets"))
    except (TypeError, ValueError):
        pockets = 0
    if pockets not in POCKETS:
        raise ValueError("Pick 4, 9, 12 or 16 pockets a page")
    slots = raw.get("slots")
    if slots is not None:
        if not isinstance(slots, list) or len(slots) > 6000:
            raise ValueError("That layout is too big")
        have = {c["n"] for c in set_cards(sid)}
        seen, clean = set(), []
        for x in slots:
            if isinstance(x, str) and x in have and x not in seen:
                seen.add(x)
                clean.append(x)
            else:
                clean.append(None)
        while clean and clean[-1] is None:
            clean.pop()
        slots = clean
    order = raw.get("order") if raw.get("order") in LAYOUT_ORDERS else "num"
    out = {"pockets": pockets, "order": order, "slots": slots}
    cover = raw.get("cover")   # the card picked for the inside cover
    if isinstance(cover, str) and cover in {c["n"] for c in set_cards(sid)}:
        out["cover"] = cover
    if raw.get("allColor") is True:   # show the cards you're missing in color too
        out["allColor"] = True
    with lock:
        write_json(sdir(sid, "layout.json"), out)
    return out


def sprite_url(num):
    num = int(num)
    if num <= 251:
        return f"{SPRITES}/versions/generation-ii/crystal/transparent/{num}.png"
    if num <= 649:
        return f"{SPRITES}/versions/generation-v/black-white/{num}.png"
    return f"{SPRITES}/{num}.png"


_logo_fail = {}


def set_logo(sid):
    """The set's logo from the card database, saved next to the binder the first time it's shown
    (the Pages view puts it on the inside cover). Set binders only. Returns its path, or None."""
    dest = sdir(sid, "logo.png")
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        return dest
    if is_multi(sid) or sid not in sets_list()["order"] or time.time() - _logo_fail.get(sid, 0) < 3600:
        return None
    try:
        _download(f"https://images.pokemontcg.io/{sid}/logo.png", dest)
        return dest
    except Exception as e:
        _logo_fail[sid] = time.time()
        log(f"{sid}: set logo: {e}")
        return None


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


UNOWN_DIR = os.path.join(DATA, "unown")
unown_lock = threading.Lock()


DEXNO_DIR = os.path.join(DATA, "dexno")
ART_DIR = os.path.join(DATA, "art")
cover_lock = threading.Lock()
_art_fail = {}


def card_dex(gids):
    """The Pokédex number of each card's Pokémon (for the binder covers). Read once per set from the
    card database and kept on the server in data/dexno/<set>.json."""
    known = {s["id"] for s in catalog()}
    by_set, out = {}, {}
    for g in gids[:6]:
        sid, _, num = g.rpartition("-")
        if sid in known and num:
            by_set.setdefault(sid, []).append((g, num))
    for sid, want in by_set.items():
        dest = os.path.join(DEXNO_DIR, sid + ".json")
        with cover_lock:
            nums = read_json(dest, None)
            if nums is None and time.time() - _art_fail.get("set:" + sid, 0) < 3600:
                continue
            if nums is None:
                try:
                    raw = json.loads(http_get(f"{GH}/cards/en/{sid}.json"))
                except Exception as e:
                    _art_fail["set:" + sid] = time.time()
                    log(f"Pokédex numbers {sid}: {e}")
                    continue
                nums = {str(c["number"]): (c.get("nationalPokedexNumbers") or [0])[0] or 0 for c in raw}
                os.makedirs(DEXNO_DIR, exist_ok=True)
                write_json(dest, nums)
        for g, num in want:
            if nums.get(num):
                out[g] = nums[num]
    return out


RARE_RANK = (("Shining", 4), ("Secret", 4), ("Crystal", 4), ("Gold Star", 4), ("Star", 4), ("Holo", 3), ("Rare", 2), ("Uncommon", 1))


def rare_rank(r):
    return next((v for k, v in RARE_RANK if k in (r or "")), 0)


def home_data():
    """Everything the home page shows: each binder with its completion and cover Pokémon (the card picked
    for the inside cover, or its most valuable Pokémon card), and the cards you got most recently."""
    sl = sets_list()
    binders, recent, want = [], [], {}
    for sid in sl["order"]:
        meta = sl["meta"].get(sid, {})
        cards = read_json(sdir(sid, "cards.json"), None)
        cards = (cards or []) + extra_list(sid) + custom_cards(sid) if cards is not None or is_own(sid) else []
        coll = read_json(sdir(sid, "collection.json"), {})
        prices = (read_json(sdir(sid, "prices.json"), {}) or {}).get("p") or {}
        names = {c["n"]: c for c in cards}
        size = binder_size(sid)
        b = {"id": sid, "name": meta.get("name", sid), "releaseDate": meta.get("releaseDate", ""),
             "printedTotal": meta.get("printedTotal", 0), "count": size if size is not None else meta.get("total", 0),
             "owned": sum(1 for n, r in coll.items() if _owned(r) and (n in names or size is None))}
        hits = sorted((c for c in cards if not c.get("custom") and (c.get("type") == "Pokémon" or is_dex(sid))),
                      key=lambda c: (-((prices.get(c["n"]) or [0])[0] or 0), -rare_rank(c.get("rarity"))))
        pick = (read_json(sdir(sid, "layout.json"), {}) or {}).get("cover")
        feat = names.get(pick) if pick in names and not names[pick].get("custom") else (hits[0] if hits else None)
        if feat:
            gid = feat["n"] if (is_multi(sid) or feat.get("extra")) else f"{sid}-{feat['n']}"
            b["cover"] = {"n": feat["n"], "name": feat.get("name", ""), "shiny": "Shining" in f"{feat.get('rarity', '')} {feat.get('name', '')}",
                          "dex": int(sid[4:]) if is_dex(sid) and sid[4:].isdigit() else 0}
            if not b["cover"]["dex"]:
                want[gid] = b["cover"]
        binders.append(b)
        for n, r in coll.items():
            if not _owned(r) or n not in names:
                continue
            d = r.get("got") or max((p.get("d") or "" for p in r.get("purchases") or [] if isinstance(p, dict)), default="")
            if d:
                recent.append({"d": d, "sid": sid, "n": n, "name": names[n].get("name", ""), "set": meta.get("name", sid)})
    gids = list(want)
    for i in range(0, len(gids), 6):
        for g, d in card_dex(gids[i:i + 6]).items():
            want[g]["dex"] = d
    recent.sort(key=lambda x: x["d"], reverse=True)
    working = [x for x in (get_settings().get("showBinders") or []) if x in sl["order"]]   # card show mode picks
    return {"binders": binders, "recent": recent[:12], "working": working}


def show_data():
    """Card show mode: every card you still need from the binders you're working on (all binders if none
    are picked), with its price and when it last sold, plus what you've bought today."""
    sl = sets_list()
    st = get_settings()
    picked = [sid for sid in (st.get("showBinders") or []) if sid in sl["order"]]
    use = picked or list(sl["order"])
    today = local_now(st).strftime("%Y-%m-%d")
    cards_out, binders = [], []
    spent, bought = 0.0, 0
    for sid in sl["order"]:
        coll = read_json(sdir(sid, "collection.json"), {})
        for r in coll.values():
            for b in (r.get("purchases") or []) if isinstance(r, dict) else []:
                if isinstance(b, dict) and b.get("d") == today:
                    bought += 1
                    spent += float(b.get("price") or 0)
        if sid not in use:
            continue
        meta = sl["meta"].get(sid, {})
        cards = read_json(sdir(sid, "cards.json"), None)
        cards = (cards or []) + extra_list(sid) + custom_cards(sid) if cards is not None or is_own(sid) else []
        pr = read_json(sdir(sid, "prices.json"), {}) or {}
        prices, info = pr.get("p") or {}, pr.get("info") or {}
        need = 0
        for c in cards:
            if _owned(coll.get(c["n"])):
                continue
            need += 1
            i = info.get(c["n"]) or {}
            cards_out.append({"sid": sid, "set": meta.get("name", sid), "n": c["n"], "name": c.get("name", ""),
                              "num": c.get("num", c["n"]),
                              "pt": c.get("pt") or ("" if is_multi(sid) or c.get("extra") or c.get("custom") else meta.get("printedTotal") or ""), "rarity": c.get("rarity", ""),
                              "custom": bool(c.get("custom")), "price": (prices.get(c["n"]) or [0])[0] or 0,
                              "src": i.get("src", ""), "last": i.get("last", "")})
        binders.append({"id": sid, "name": meta.get("name", sid), "need": need})
    return {"picked": picked, "binders": binders, "cards": cards_out, "today": today,
            "bought": bought, "spent": round(spent, 2)}


def pokemon_art(num, shiny=False):
    """A Pokémon's official Ken Sugimori artwork (the art the vintage binders used), downloaded once from
    PokeAPI and kept on the server. Shiny colors for Shining cards."""
    num = int(num)
    if not 1 <= num <= 1025:
        raise ValueError("no such Pokémon")
    name = f"{num}{'s' if shiny else ''}"
    dest = os.path.join(ART_DIR, name + ".png")
    with cover_lock:
        if not (os.path.exists(dest) and os.path.getsize(dest) > 0):
            if time.time() - _art_fail.get(name, 0) < 3600:   # don't ask again for an hour after a failure
                raise ValueError("not available right now")
            os.makedirs(ART_DIR, exist_ok=True)
            try:
                _download(f"{SPRITES}/other/official-artwork/{'shiny/' if shiny else ''}{num}.png", dest)
            except Exception:
                _art_fail[name] = time.time()
                raise
    return dest


def unown_sprite(letter):
    """An Unown letter sprite for the binder-complete celebration, downloaded once and kept on the server."""
    dest = os.path.join(UNOWN_DIR, letter + ".png")
    with unown_lock:
        if not (os.path.exists(dest) and os.path.getsize(dest) > 0):
            name = "201" if letter == "a" else f"201-{letter}"
            body = http_get(f"{SPRITES}/versions/generation-ii/crystal/transparent/{name}.png")
            os.makedirs(UNOWN_DIR, exist_ok=True)
            with open(dest + ".tmp", "wb") as f:
                f.write(body)
            os.replace(dest + ".tmp", dest)
    return dest


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
        (sl.get("removed") or {}).pop(sid, None)
        meta["added"] = int(time.time())
        sl["meta"][sid] = meta
        write_json(SETS_FILE, sl)
    fetch_sprite(sid)
    first_refresh_later(sid)
    log(f"Added master set {name} ({len(cards)} cards)")
    return meta


def sets_list():
    return read_json(SETS_FILE, {"order": [], "meta": {}})


def add_set(sid):
    if is_dex(sid):
        return add_dex(sid)
    if is_own(sid):
        raise ValueError("Make your own binder with My own binder")
    meta = next((s for s in catalog() if s["id"] == sid), None)
    if not meta:
        raise ValueError("Unknown set")
    cards = set_cards(sid)
    with lock:
        sl = sets_list()
        if sid not in sl["order"]:
            sl["order"].append(sid)
        (sl.get("removed") or {}).pop(sid, None)
        meta = dict(meta, added=int(time.time()))
        sl["meta"][sid] = meta
        write_json(SETS_FILE, sl)
    first_refresh_later(sid)
    log(f"Added set {meta['name']} ({len(cards)} cards)")
    return meta


FIRST_REFRESH_WAIT = 120   # a new binder's first price check waits this long, in case it's a quick test that gets removed


def first_refresh_later(sid, wait=FIRST_REFRESH_WAIT):
    def go():
        time.sleep(wait)
        for _ in range(120):   # wait for another refresh to finish (up to an hour)
            if sid not in sets_list()["order"]:
                log(f"{sid}: removed before its first price check, skipped")
                return
            if refresh_prices(sid, "new binder") is not False:
                return
            time.sleep(30)
    threading.Thread(target=go, daemon=True).start()


KEEP_REMOVED_DAYS = 30   # a removed binder can be brought back (with everything in it) for this long


def remove_set(sid):
    """Take a binder off the list. Its data stays for KEEP_REMOVED_DAYS so it can be restored."""
    with lock:
        sl = sets_list()
        if sid in sl["order"]:
            pos = sl["order"].index(sid)
            sl["order"].remove(sid)
            sl.setdefault("removed", {})[sid] = {"at": int(time.time()), "pos": pos}
        write_json(SETS_FILE, sl)


def restore_set(sid):
    """Put a removed binder back where it was."""
    with lock:
        sl = sets_list()
        info = (sl.get("removed") or {}).pop(sid, None)
        if info is None and sid not in sl["order"]:
            raise ValueError("That binder can't be restored any more")
        if sid not in sl["order"]:
            pos = info.get("pos", len(sl["order"])) if isinstance(info, dict) else len(sl["order"])
            sl["order"].insert(max(0, min(int(pos), len(sl["order"]))), sid)
        write_json(SETS_FILE, sl)
    start_images(sid)
    return sl["meta"].get(sid, {"id": sid, "name": sid})


def removed_sets():
    """Binders removed in the last KEEP_REMOVED_DAYS: [{id, name, at, daysLeft}], newest first."""
    sl = sets_list()
    now = time.time()
    out = []
    for sid, info in (sl.get("removed") or {}).items():
        at = info.get("at", 0) if isinstance(info, dict) else 0
        left = KEEP_REMOVED_DAYS - int((now - at) // DAY)
        if sid not in sl["order"] and left > 0:
            out.append({"id": sid, "name": sl["meta"].get(sid, {}).get("name", sid), "at": at, "daysLeft": left})
    return sorted(out, key=lambda x: -x["at"])


def saved_cards(sid):
    """What a binder that isn't on the list still has saved (from being removed earlier), or None.
    {owned, name, at} so adding it again can ask: bring those cards back, or start fresh?"""
    sl = sets_list()
    if sid in sl["order"]:
        return None
    coll = read_json(sdir(sid, "collection.json"), {})
    owned = sum(1 for r in (coll.values() if isinstance(coll, dict) else [])
                if isinstance(r, dict) and ((_is_num(r.get("qty")) and r["qty"] > 0) or r.get("purchases")))
    if not owned:
        return None
    info = (sl.get("removed") or {}).get(sid)
    return {"owned": owned, "name": sl["meta"].get(sid, {}).get("name", sid),
            "at": info.get("at", 0) if isinstance(info, dict) else 0}


FRESH_FILES = (("collection", {}), ("shop", {}), ("custom", []), ("extra", []), ("layout", None))


def start_fresh(sid):
    """Clear the cards a removed binder left behind (owned cards, purchases, notes, photos, shopping list,
    added cards, page layout) so adding it again starts empty. Prices and price history stay. Backs up first."""
    auto_backup("before-fresh")
    with lock:
        with tx():
            for kind, empty in FRESH_FILES:
                if data_exists(sdir(sid, kind + ".json")):
                    write_json(sdir(sid, kind + ".json"), empty)
        shutil.rmtree(sdir(sid, "photos"), ignore_errors=True)
    log(f"{sid}: started fresh, cleared the cards saved from before")


def add_set_again(sid, keep):
    """Add a binder, deciding what happens to cards saved from an earlier removal.
    keep=None: ask (raises SavedCards when there's something saved); True: bring them back; False: start empty."""
    saved = saved_cards(sid)
    if saved and keep is None:
        raise SavedCards(saved)
    if saved and keep:
        if sid in (sets_list().get("removed") or {}):
            meta = restore_set(sid)
            return dict(meta, restored=True)
        return dict(add_set(sid), restored=True)
    if saved and keep is False:
        start_fresh(sid)
    return add_set(sid)


class SavedCards(Exception):
    def __init__(self, saved):
        super().__init__("This binder still has cards saved from before")
        self.saved = saved


def purge_removed():
    """Delete binders that were removed more than KEEP_REMOVED_DAYS ago (data, pictures and photos)."""
    with lock:
        sl = sets_list()
        removed = sl.get("removed") or {}
        now = time.time()
        gone = [sid for sid, info in removed.items()
                if sid in sl["order"] or now - (info.get("at", 0) if isinstance(info, dict) else 0) > KEEP_REMOVED_DAYS * DAY]
        if not gone:
            return []
        with tx() as c:
            for sid in gone:
                removed.pop(sid, None)
                if sid in sl["order"]:
                    continue   # it was added again, keep it
                for table in ("collection", "prices", "history"):
                    c.execute(f"DELETE FROM {table} WHERE sid = ?", (sid,))
                c.execute("DELETE FROM docs WHERE key LIKE ?", (f"sets/{sid}/%",))
                sl["meta"].pop(sid, None)
            sl["removed"] = removed
            write_json(SETS_FILE, sl)
        for sid in gone:
            if sid not in sl["order"] and re.fullmatch(SID_RE, sid):
                shutil.rmtree(sdir(sid), ignore_errors=True)
                log(f"{sid}: removed {KEEP_REMOVED_DAYS}+ days ago, deleted for good")
        return gone


# ---------- images ----------

# Card pictures come in two sizes from the card database: a small one (about 245x342) for the grid and lists,
# and the full scan (about 734x1024) for card details. Each is downloaded the first time it's looked at,
# so a binder you add and remove again to try something out only fetches the few pictures you saw.
# Binders kept for an hour or more get their small pictures filled in quietly in the background.
FILL_AFTER = 3600
_img_fail = {}   # (sid, n, full) -> when a download last failed, so a missing picture isn't retried on every view


def image_path(sid, n, full=True):
    return sdir(sid, "images", f"{n}.png") if full else sdir(sid, "images", "s", f"{n}.png")


def small_url(url):
    """The card database names the full scan 1_hires.png and the small picture 1.png."""
    return url[:-len("_hires.png")] + ".png" if url.endswith("_hires.png") else url


def _download(url, dest):
    body = http_get(url, timeout=20)
    if not body:
        raise ValueError("empty picture")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = f"{dest}.{threading.get_ident()}.tmp"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, dest)


def fetch_image(sid, card, full=False):
    """Make sure one card picture is on the server. Returns its path, or None."""
    n = card["n"]
    dest = image_path(sid, n, full)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    url = card.get("img") or ""
    if not url.startswith("http"):
        return None
    key = (sid, n, full)
    if time.time() - _img_fail.get(key, 0) < 600:
        return None
    try:
        _download(url if full else small_url(url), dest)
        _img_fail.pop(key, None)
        return dest
    except Exception as e:
        _img_fail[key] = time.time()
        log(f"image {sid}-{n}{' (full)' if full else ''}: {e}")
        return None


def card_image(sid, n, full=False):
    """The picture to show for one card, downloading it now if needed. The small picture falls back to the full scan."""
    path = image_path(sid, n, full)
    if os.path.isfile(path):
        return path
    card = next((c for c in set_cards(sid) if c["n"] == n), None)
    got = fetch_image(sid, card, full) if card else None
    if got:
        return got
    if not full and os.path.isfile(image_path(sid, n, True)):
        return image_path(sid, n, True)   # older binders already have the full scans
    return None


def binder_age(sid):
    added = (sets_list()["meta"].get(sid) or {}).get("added")
    return time.time() - added if isinstance(added, (int, float)) else FILL_AFTER   # older binders: kept long enough


def download_images(sid):
    """Background fill of the small pictures for a binder that's been kept a while."""
    try:
        cards = [c for c in set_cards(sid) if (c.get("img") or "").startswith("http")]
        missing = [c for c in cards if not os.path.exists(image_path(sid, c["n"], False))]
        if not missing:
            return
        log(f"{sid}: downloading {len(missing)} card pictures...")
        img_jobs[sid] = {"done": 0, "total": len(missing)}
        ok = 0
        for i, c in enumerate(missing):
            if sid not in sets_list()["order"]:
                log(f"{sid}: binder removed, stopped downloading pictures")
                return
            img_jobs[sid]["done"] = i
            ok += bool(fetch_image(sid, c, False))
            time.sleep(0.2)
        log(f"{sid}: card pictures {ok} of {len(missing)} downloaded.")
    finally:
        img_jobs.pop(sid, None)


def start_images(sid, now=False):
    """Fill in a binder's small pictures in the background. Waits until a new binder has been kept an hour,
    unless you ask for it now (sets menu > Edit > Get pictures)."""
    if sid in img_jobs or (not now and binder_age(sid) < FILL_AFTER):
        return
    img_jobs[sid] = {"done": 0, "total": 0}
    threading.Thread(target=download_images, args=(sid,), daemon=True).start()


def pictures_saved(sid, cards=None):
    """How many of a binder's small pictures are saved on the server: (saved, total)."""
    cards = set_cards(sid) if cards is None else cards
    want = [c["n"] for c in cards if (c.get("img") or "").startswith("http")]
    d = sdir(sid, "images", "s")
    have = set(os.listdir(d)) if os.path.isdir(d) else set()
    return sum(1 for n in want if f"{n}.png" in have), len(want)


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


def daily_cards(sid, cards, day=None):
    """Which cards the nightly refresh checks: every card you own, plus a third of the rest, taking turns,
    so each card you still need is checked every 3 days. Roughly halves the nightly time.
    (Settings > Daily refresh can check every card every night instead.)"""
    coll = read_json(sdir(sid, "collection.json"), {})
    coll = coll if isinstance(coll, dict) else {}
    turn = (day if day is not None else datetime.now().toordinal()) % 3
    out, i = [], 0
    for c in cards:
        rec = coll.get(c["n"]) if isinstance(coll.get(c["n"]), dict) else {}
        if (rec.get("qty") or 0) > 0 or c.get("custom"):
            out.append(c)
        else:
            if i % 3 == turn:
                out.append(c)
            i += 1
    return out


def refresh_prices(sid, reason="daily", only_daily=False, only=None):
    with job_lock:
        if job["running"] or big["what"]:
            return False
        name = sets_list()["meta"].get(sid, {}).get("name", sid)
        job.update(running=True, set=sid, name=name, done=0, total=0, priced=0, message="")
    try:
        cards = set_cards(sid)
        if only_daily:
            cards = daily_cards(sid, cards)
        if only:
            cards = [c for c in cards if c["n"] in only]
        job["total"] = len(cards)
        log(f"{sid}: price refresh started ({reason}, {len(cards)} cards).")
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
        info = prices.get("info") or {}
        fresh = {}   # what this refresh found; merged into the newest prices.json at the end
        priced = 0
        for i, c in enumerate(cards):
            job["done"] = i
            if i % 5 == 0 and sid not in sets_list()["order"]:
                break   # the binder was removed: stop asking the price sites about it
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
            if main_price(inf, slots, backup):
                priced += 1
                job["priced"] = priced
            fresh[n] = inf
            time.sleep(1)
        job["done"] = len(cards)
        write_json(sdir(sid, "tcg_ids.json"), ids)
        if graded_on:
            write_json(sdir(sid, "pc_urls.json"), pc_cache)
        if backup:
            write_json(sdir(sid, "tcgdex_ids.json"), dex_ids)
        # A refresh takes minutes. Anything that changed prices.json meanwhile (new price options, a restore)
        # is kept: read the newest copy, add this refresh's results, and work out main prices with today's options.
        with lock:
            if sid not in sets_list()["order"]:
                job["message"] = f"{name} was removed during the refresh."
                return True
            prices = read_json(sdir(sid, "prices.json"), {})
            p = prices.setdefault("p", {})
            info = prices.setdefault("info", {})
            slots_now, backup_now = set_slots(sid), get_settings().get("backup", True)
            priced = 0
            for n, inf in fresh.items():
                mp = main_price(inf, slots_now, backup_now)
                if mp:
                    p[n] = [mp[0]]
                    inf.update(src=mp[3], count=mp[1], last=mp[2])
                    inf.pop("note", None)
                    priced += 1
                else:
                    inf["note"] = "No recent sales for your price options; kept last price"
                info[n] = inf
            job["priced"] = priced
            prices["lastRun"] = int(time.time())
            if priced:
                prices["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            write_json(sdir(sid, "prices.json"), prices)
            snapshot_history(sid, prices)
        job["message"] = (f"{name}: got prices for the card you added." if only and len(cards) == 1
                          else f"{name}: updated {priced} of {len(cards)} prices.")
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


def srv_name():
    """What messages call the computer the binder runs on: your name for it from Settings, or "the server"."""
    return (get_settings().get("serverName") or "").strip() or "the server"


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
    every = bool(get_settings().get("refreshAll"))
    for sid in list(sets_list()["order"]):
        for _ in range(240):   # wait (up to an hour) for another check, an update or a restore to finish
            if sid not in sets_list()["order"] or refresh_prices(sid, reason, only_daily=not every) is not False:
                break
            time.sleep(15)


# ---------- price history, purchases, spending ----------

def today_local():
    return local_now(get_settings()).strftime("%Y-%m-%d")


def snapshot_history(sid, prices=None):
    """Save today's LP/MP price for every card (one entry per day; the latest refresh wins)."""
    prices = prices if prices is not None else read_json(sdir(sid, "prices.json"), {})
    p = prices.get("p") or {}
    if not p:
        return
    history_put_day(sid, today_local(), {n: v[0] for n, v in p.items() if v and isinstance(v[0], (int, float))})


TREND_DAYS = (1, 7, 30, 90, 365)   # the price change periods the page offers (plus "all time")


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def set_trends(sid, today):
    """Everything the page needs to show price changes, without sending every saved day:
    for each card, its first and last saved price, how many days have one, and the price as it stood
    1, 7, 30, 90 and 365 days before `today`. Stays the same size however long history grows."""
    base = datetime.strptime(today, "%Y-%m-%d").date()
    cuts = [(str(p), (base - timedelta(days=p)).isoformat()) for p in TREND_DAYS]
    hist = read_json(sdir(sid, "history.json"), {})
    hist = hist if isinstance(hist, dict) else {}
    cards, first = {}, ""
    for d in sorted(hist):
        first = first or d
        day = hist[d]
        if not isinstance(day, dict):
            continue
        for n, v in day.items():
            if not _is_num(v):
                continue
            c = cards.get(n)
            if c is None:
                c = cards[n] = {"first": [d, v], "count": 0, "at": {}}
            c["count"] += 1
            c["last"] = [d, v]
            for p, cut in cuts:
                if d <= cut:
                    c["at"][p] = [d, v]
    return {"first": first, "today": today, "cards": cards}


def card_series(sid, n):
    """[[date, price], ...] for one card, oldest first (for its price chart)."""
    key = f"sets/{sid}/history.json"
    with db_lock:
        row = db().execute("SELECT body FROM docs WHERE key = ?", (key,)).fetchone()
        if row is not None and "__raw" not in json.loads(row[0]):
            return [[d, v] for d, v, t in db().execute(
                "SELECT d, json_extract(snap, ?), json_type(snap, ?) FROM history WHERE sid = ? ORDER BY d",
                (f'$."{n}"', f'$."{n}"', sid)) if t in ("integer", "real")]
    hist = read_json(sdir(sid, "history.json"), {})
    hist = hist if isinstance(hist, dict) else {}
    return [[d, hist[d][n]] for d in sorted(hist) if isinstance(hist[d], dict) and _is_num(hist[d].get(n))]


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
        cards = {c["n"]: c["name"] for c in (read_json(sdir(sid, "cards.json"), None) or []) + extra_list(sid)}
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

    today = today_local()
    dates.add(today)
    timeline = []
    # Walk the dates in order once, keeping each card's latest known price (much faster than
    # searching the whole history for every card on every date, which slowed down as history grew).
    pos = {sid: 0 for sid in hist_by_set}
    known = {sid: {} for sid in hist_by_set}
    buys = sorted((r["d"], r["price"]) for r in log_rows)
    bi, spent = 0, 0.0
    for d in sorted(dates):
        while bi < len(buys) and (not buys[bi][0] or buys[bi][0] <= d):
            spent += buys[bi][1]
            bi += 1
        for sid, hist in hist_by_set.items():
            while pos[sid] < len(hist) and hist[pos[sid]][0] <= d:
                known[sid].update(hist[pos[sid]][1])
                pos[sid] += 1
        value = 0.0
        for sid, n, q, acq, ratio in owned:
            if not acq or acq <= d:
                if d == today:
                    p = cur_by_set[sid].get(n, 0)
                else:
                    p = known[sid].get(n)
                    p = cur_by_set[sid].get(n, 0) if p is None else p
                value += p * ratio * q
        timeline.append({"d": d, "spent": round(spent, 2), "value": round(value, 2)})
    log_rows.sort(key=lambda r: (r["d"] or "0000"), reverse=True)
    return {"totals": {"spent": round(total_spent, 2), "value": timeline[-1]["value"] if timeline else 0,
                       "undated": undated, "purchases": len(log_rows)},
            "months": [dict(m, spent=round(m["spent"], 2)) for m in sorted(months.values(), key=lambda m: m["m"])],
            "timeline": timeline, "log": log_rows, "today": today}


STARTED = time.time()
PROBLEM_RE = re.compile(r"failed|error|couldn't|can't|refused|timed out|unreachable", re.I)


# Picture downloads that missed (card pictures, set logos, Pokémon artwork) are retried later by themselves
# and some sets simply have no logo, so they aren't listed as problems in Status.
PICTURE_MISS_RE = re.compile(r"^(image |Pokémon art |[\w-]+: set logo: )")


def health():
    """Quick self-check: the web server answers and the database can be read."""
    try:
        with db_lock:
            db().execute("SELECT 1").fetchone()
        return {"ok": True, "version": APP_VERSION, "uptime": int(time.time() - STARTED)}
    except Exception as e:
        return {"ok": False, "version": APP_VERSION, "error": str(e)}


def status():
    """What Settings > About > Status shows."""
    sl = sets_list()
    last = 0
    for sid in sl["order"]:
        pr = read_json(sdir(sid, "prices.json"), {})
        if not isinstance(pr, dict):
            continue
        if isinstance(pr.get("lastRun"), (int, float)):
            last = max(last, pr["lastRun"])
        elif isinstance(pr.get("updated"), str):  # binders priced before v3.5 only have the date
            try:
                last = max(last, datetime.strptime(pr["updated"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            except ValueError:
                pass
    backups = list_auto_backups()
    size = sum(os.path.getsize(DB_FILE + ext) for ext in ("", "-wal") if os.path.exists(DB_FILE + ext))
    pics = 0
    for sid in sl["order"]:
        for sub in ("", "s"):
            d = sdir(sid, "images", sub) if sub else sdir(sid, "images")
            if os.path.isdir(d):
                pics += sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d) if f.endswith(".png"))
    try:
        du = shutil.disk_usage(DATA)
        free = du.free
    except OSError:
        free = None
    day_ago = time.time() - DAY
    problems = [{"at": int(t), "msg": m[:200]} for t, m in LOG_TAIL if t > day_ago and PROBLEM_RE.search(m) and not PICTURE_MISS_RE.search(m)][-5:]
    return {"version": APP_VERSION, "uptime": int(time.time() - STARTED), "lastRefresh": int(last),
            "refreshing": bool(job["running"]), "lastBackup": backups[0] if backups else None,
            "dbSize": size, "pictures": pics, "freeSpace": free, "problems": problems,
            "settings": {k: get_settings().get(k) for k in ("auto", "time", "refreshAll")}}


def watchdog():
    """If the binder stops answering its own pages for about 6 minutes, restart it (your data is safe on disk)."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    misses = 0
    time.sleep(120)
    while True:
        try:
            with opener.open(f"http://127.0.0.1:{PORT}/api/health", timeout=20) as r:
                misses = 0 if r.status == 200 else misses + 1
        except Exception:
            misses += 1
        if misses >= 3:
            log("The binder stopped answering for several minutes. Restarting it.")
            restart_self()
        time.sleep(120)


def safely(label, fn, *args):
    """Run one background step; an error is logged instead of stopping everything after it."""
    try:
        return fn(*args)
    except Exception as e:
        log(f"{label} failed: {e}")


def housekeeping():
    """Every 30 minutes: tidy up, save the daily backup, retry missing pictures, look for new sets and shows."""
    safely("freeing the card index", release_card_index)
    safely("cleanup of removed binders", purge_removed)
    safely("daily backup", lambda: daily_backup_due() and auto_backup("daily"))
    for sid in list(sets_list()["order"]):
        safely(f"{sid}: picture retry", start_images, sid)   # retries any pictures that failed earlier
    if os.path.exists(DEX_INDEX):
        safely("master set index", start_dex_index)   # picks up new sets for master set binders (about once a month)
    if safely("card show check", shows_due) and not shows_job["running"]:
        threading.Thread(target=scan_shows, args=("weekly",), daemon=True).start()


def scheduler():
    """Runs for as long as the binder does. Each step is guarded, so one error can't stop the nightly
    price check or the daily backup for good. The nightly check runs on its own, so housekeeping keeps going during it."""
    time.sleep(15)
    ticks = 0
    while True:
        if ticks % 30 == 0:
            safely("housekeeping", housekeeping)
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
                threading.Thread(target=safely, args=("scheduled price refresh", refresh_all, "scheduled"), daemon=True).start()
        except Exception as e:
            log(f"scheduler: {e}")
        time.sleep(60)


# ---------- first start: move the original Neo Destiny files into data/sets/neo4 ----------

def clean_leftovers(age=3600):
    """Delete temporary files left behind when the binder was stopped partway through something
    (an update test start, a restore upload, a backup being written, a picture download). Runs at start."""
    cutoff, freed, count = time.time() - age, 0, 0

    def drop(path):
        nonlocal freed, count
        try:
            if os.path.getmtime(path) > cutoff:
                return   # might still be in use
            if os.path.isdir(path):
                size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(path) for f in fs)
                shutil.rmtree(path)
            else:
                size = os.path.getsize(path)
                os.remove(path)
            freed += size
            count += 1
        except OSError:
            pass
    for f in os.listdir(APP):
        if f.startswith(".trial-") or (f.startswith("tmp") and f.endswith(".zip")) or f.endswith(".tmp"):
            drop(os.path.join(APP, f))
    for root, dirs, files in os.walk(DATA):
        for f in files:
            if f.endswith(".tmp"):
                drop(os.path.join(root, f))
    if os.path.isdir(BACKUPS):
        for f in os.listdir(BACKUPS):
            if f.endswith(".tmp"):
                drop(os.path.join(BACKUPS, f))
    if count:
        log(f"Cleaned up {count} leftover temporary file{'s' if count != 1 else ''} ({freed / 1048576:.1f} MB).")
    return count


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
    migrate_to_db()
    sl = sets_list()
    if not sl["order"]:
        # first run on a fresh install, or right after the move above
        if not data_exists(sdir("neo4", "collection.json")):
            for name, dest in (("seed_collection.json", "collection.json"), ("seed_prices.json", "prices.json")):
                seed = read_file_json(os.path.join(APP, name), None)
                if seed is not None:
                    write_json(sdir("neo4", dest), seed)
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
        keep = shows_keep_from()
        with lock:
            cur = shows_state()   # newest copy, so town or weekly-scan changes made during the scan are kept
            cur["shows"] = {k: v for k, v in shows.items() if v["date"] >= keep}   # drop shows older than yesterday
            cur.setdefault("firstScan", now)   # shows found on the very first scan aren't marked new
            cur.update(scanned=now, lastNew=new, error="")
            write_json(SHOWS_FILE, cur)
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


def shows_keep_from():
    """Shows stay listed through the day after they happen, so a show on the day a scan runs (or one that ran
    late into the night) doesn't vanish. Older ones are dropped."""
    return (local_now(get_settings()) - timedelta(days=1)).strftime("%Y-%m-%d")


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
    cards = (read_json(sdir(sid, "cards.json"), None) or []) + extra_list(sid) + custom_list(sid)
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


def _xlsx(sheets):
    """A small Excel file (standard library only): sheets = [(name, header, rows)], first row bold and frozen."""
    from xml.sax.saxutils import escape
    def col(i):
        s = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s
    def cell(ref, v, style=0):
        st = f' s="{style}"' if style else ""
        if isinstance(v, bool) or v is None or v == "":
            return f'<c r="{ref}"{st}/>' if style else ""
        if isinstance(v, (int, float)):
            return f'<c r="{ref}"{st}><v>{v}</v></c>'
        return f'<c r="{ref}"{st} t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'
    files, used = {}, set()
    names = []
    for k, (name, header, rows, money) in enumerate(sheets, 1):
        nm = re.sub(r"[\\/?*\[\]:]", "", name)[:31] or f"Sheet{k}"
        base, n = nm, 2
        while nm.lower() in used:
            nm = (base[:28] + f" {n}"); n += 1
        used.add(nm.lower()); names.append(nm)
        widths = [max(len(str(h)), *(len(str(r[i])) for r in rows[:500]) if rows else [0]) for i, h in enumerate(header)]
        cols = "".join(f'<col min="{i+1}" max="{i+1}" width="{min(48, max(8, w + 2))}" customWidth="1"/>' for i, w in enumerate(widths))
        body = ['<row r="1">' + "".join(cell(f"{col(i)}1", h, 1) for i, h in enumerate(header)) + "</row>"]
        for j, r in enumerate(rows, 2):
            body.append(f'<row r="{j}">' + "".join(cell(f"{col(i)}{j}", v, 2 if i in money and isinstance(v, (int, float)) else 0) for i, v in enumerate(r)) + "</row>")
        files[f"xl/worksheets/sheet{k}.xml"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            f'<cols>{cols}</cols><sheetData>{"".join(body)}</sheetData></worksheet>')
    n = len(names)
    files["[Content_Types].xml"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + "".join(f'<Override PartName="/xl/worksheets/sheet{k}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for k in range(1, n + 1))
        + "</Types>")
    files["_rels/.rels"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    files["xl/workbook.xml"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + "".join(f'<sheet name="{escape(nm, {chr(34): "&quot;"})}" sheetId="{k}" r:id="rId{k}"/>' for k, nm in enumerate(names, 1)) + "</sheets></workbook>")
    files["xl/_rels/workbook.xml.rels"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(f'<Relationship Id="rId{k}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{k}.xml"/>' for k in range(1, n + 1))
        + f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    files["xl/styles.xml"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00"/></numFmts>'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels", "xl/styles.xml"):
            z.writestr(name, files[name])
        for k in range(1, n + 1):
            z.writestr(f"xl/worksheets/sheet{k}.xml", files[f"xl/worksheets/sheet{k}.xml"])
    return out.getvalue()


def export_collection():
    """Every binder in one Excel file: an "All binders" sheet plus one sheet per binder."""
    sl = sets_list()
    header = ["Binder", "Set", "Number", "Card", "Rarity", "Status", "Copies", "Condition", "Paid", "Price each", "Value", "First owned", "Notes"]
    money = {8, 9, 10}
    every, per = [], []
    for sid in sl["order"]:
        meta = sl["meta"].get(sid, {})
        bname = meta.get("name", sid)
        coll = read_json(sdir(sid, "collection.json"), {})
        prices = (read_json(sdir(sid, "prices.json"), {}) or {}).get("p") or {}
        rows = []
        cards = read_json(sdir(sid, "cards.json"), None)
        cards = (cards or []) + extra_list(sid) + custom_cards(sid)
        for c in cards:
            rec = coll.get(c["n"]) or {}
            qty = int(rec.get("qty") or 0) if isinstance(rec.get("qty"), (int, float)) else 0
            paid = round(sum(b.get("price") or 0 for b in rec.get("purchases") or [] if isinstance(b, dict) and isinstance(b.get("price"), (int, float))), 2)
            each = (prices.get(c["n"]) or [0])[0] or 0
            first = (rec.get("got") or "")[:10] or min((b.get("d") or "" for b in rec.get("purchases") or [] if isinstance(b, dict) and b.get("d")), default="")
            setname = c.get("set") or (bname if not (is_multi(sid) or c.get("extra")) else "")
            num = c.get("num") or c["n"]
            rows.append([bname, setname, num, c.get("name", ""), c.get("rarity", ""), "Owned" if qty > 0 else "Need", qty,
                         rec.get("cond") or "", paid or "", round(each, 2) if each else "", round(each * qty, 2) if each and qty else "",
                         first if qty > 0 else "", rec.get("note") or ""])
        every += rows
        per.append((bname, header, rows, money))
    return _xlsx([("All binders", header, every, money)] + per)


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
AUTO_KEEP = {"before-update": 10, "before-import": 5, "before-restore": 5, "before-sync": 5, "before-fresh": 5, "daily": 7}
AUTO_NAME_RE = re.compile(r"(before-(?:update|import|restore|sync|fresh)|daily)-\d{8}-\d{6}(?:-\d{3})?\.zip")


def backup_kind(k):
    return k[7:] if k.startswith("before-") else k
MAX_RESTORE = 500 * 1024 * 1024
BACKUP_RE = re.compile(rf"(settings\.json|sets\.json|shows\.json|favicon|favicon\.json|sets/{SID_RE}/(?:{'|'.join(SET_FILES)})\.json"
                       rf"|sets/{SID_RE}/photos/{NUM_RE}(?:_back)?(?:\.json)?)")


def backup_files():
    """Files a backup holds next to the database's data: your photos and tab icon.
    Card images and the set catalog are left out because they download again by themselves."""
    out = [name for name in ("favicon", "favicon.json") if os.path.isfile(os.path.join(DATA, name))]
    sets_root = os.path.join(DATA, "sets")
    for sid in sorted(os.listdir(sets_root)) if os.path.isdir(sets_root) else []:
        pdir = sdir(sid, "photos")
        for f in sorted(os.listdir(pdir)) if os.path.isdir(pdir) else []:
            out.append(f"sets/{sid}/photos/{f}")
    return [n for n in out if BACKUP_RE.fullmatch(n)]


def make_backup(target):
    """A zip of your data as JSON files (the same layout every version uses), plus photos and the tab icon."""
    with lock:
        with db_lock:   # one consistent moment: nothing can save while this reads
            docs = [(k, db_read(k)) for k in db_keys() if BACKUP_RE.fullmatch(k)]
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("backup.json", json.dumps({"app": "pokemon-binder", "version": APP_VERSION, "created": now_iso()}))
            for k, obj in docs:
                z.writestr(k, json.dumps(obj, indent=1))
            for name in backup_files():
                z.write(os.path.join(DATA, name), name)


def auto_backup(kind):
    """Save a backup of all binder data in backups/ on the server before something that changes it a lot
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
    what = {"fresh": "starting a binder fresh"}.get(backup_kind(kind), backup_kind(kind))
    log(f"Saved a {'daily backup' if kind == 'daily' else 'backup before ' + what}: backups/{name}")
    return name


def daily_backup_due():
    """True if today's daily backup hasn't been made yet (the newest 7 are kept)."""
    today = time.strftime("%Y%m%d")
    have = os.listdir(BACKUPS) if os.path.isdir(BACKUPS) else []
    return not any(f.startswith("daily-" + today) for f in have)


# ---------- phone app: changes made offline ----------
# Offline the phone can only ADD: mark a card owned and/or add one purchase (price paid, where, seller).
# Each purchase carries an id made on the phone, so sending the same change twice never adds it twice.
SYNC_ID_RE = re.compile(r"[a-z0-9]{6,40}")


def clean_sync_change(ch):
    sid, n, p = ch.get("sid"), ch.get("n"), ch.get("purchase")
    if not (isinstance(sid, str) and re.fullmatch(SID_RE, sid) and isinstance(n, str) and re.fullmatch(NUM_RE, n)):
        raise ValueError("A change names a card the binder doesn't know")
    if not isinstance(p, dict) or not isinstance(p.get("id"), str) or not SYNC_ID_RE.fullmatch(p["id"]):
        raise ValueError("A change is missing its purchase")
    d = p.get("d") or ""
    if d and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d)):
        raise ValueError("A purchase date doesn't look right")
    price = p.get("price")
    if price is not None:
        price = round(float(price), 2)
        if not 0 <= price < 1e7:
            raise ValueError("A purchase price doesn't look right")
    out = {"id": p["id"], "d": d, "price": price, "where": str(p.get("where") or "")[:60]}
    sel = p.get("seller")
    if isinstance(sel, dict) and isinstance(sel.get("p"), str) and isinstance(sel.get("h"), str) and sel["h"].strip():
        out["seller"] = {"p": sel["p"][:20], "h": sel["h"].strip()[:100]}
    if ch.get("cond") in RAW_CONDS:
        out["_cond"] = ch["cond"]   # the copy's condition (card show mode); set on the card, not kept in the purchase
    return sid, n, out


def add_one_purchase(sid, n, purchase):
    """Add one purchase to a card (needs the lock). False if that purchase id is already there.
    A condition sent with it becomes the card's condition when this is the first copy."""
    purchase = dict(purchase)
    cond = purchase.pop("_cond", None)
    rec = read_json(sdir(sid, "collection.json"), {}).get(n)
    rec = dict(rec) if isinstance(rec, dict) else {}
    buys = [b for b in rec.get("purchases") or [] if isinstance(b, dict)]
    if any(b.get("id") == purchase["id"] for b in buys):
        return False
    first = not _owned(rec)
    buys.append(purchase)
    buys.sort(key=lambda b: b.get("d") or "")
    rec["purchases"] = buys
    rec["qty"] = len(buys)
    if cond and (first or not rec.get("cond")):
        rec["cond"] = cond
    collection_put(sid, n, rec)
    return True


def apply_sync(changes):
    """Add the phone's offline purchases. Saves a backup first and remembers what was added, for Undo last sync."""
    cleaned = [clean_sync_change(ch) for ch in changes if isinstance(ch, dict)]
    if not cleaned:
        return {"applied": 0, "skipped": 0}
    order = sets_list()["order"]
    if any(sid not in order for sid, _, _ in cleaned):
        raise ValueError("A change is for a binder that isn't on the server any more")
    def already(sid, n, pid):
        rec = read_json(sdir(sid, "collection.json"), {}).get(n)
        return isinstance(rec, dict) and any(isinstance(b, dict) and b.get("id") == pid for b in rec.get("purchases") or [])
    if all(already(sid, n, p["id"]) for sid, n, p in cleaned):
        return {"applied": 0, "skipped": len(cleaned)}   # all sent before: nothing to do, keep the last sync's Undo
    backup = auto_backup("before-sync")
    added, skipped = [], 0
    with lock:
        for sid, n, purchase in cleaned:
            if not add_one_purchase(sid, n, purchase):
                skipped += 1      # already sent once
                continue
            added.append({"sid": sid, "n": n, "id": purchase["id"]})
        at = now_iso()
        if added:
            st = read_json(SETTINGS, {})
            st["lastSync"] = {"at": at, "backup": backup, "added": added}
            write_json(SETTINGS, st)
    log(f"Phone sync: added {len(added)} purchase(s), {skipped} already there. Backup: backups/{backup}")
    return {"applied": len(added), "skipped": skipped, "backup": backup, "at": at}


def undo_sync():
    """Undo last sync: take out exactly the purchases that sync added (anything changed since stays)."""
    with lock:
        st = read_json(SETTINGS, {})
        last = st.get("lastSync") or {}
        if not last.get("added") or last.get("undone"):
            raise ValueError("There's no sync to undo")
        removed = 0
        for a in last["added"]:
            rec = read_json(sdir(a["sid"], "collection.json"), {}).get(a["n"])
            if not isinstance(rec, dict):
                continue
            buys = [b for b in rec.get("purchases") or [] if isinstance(b, dict)]
            keep = [b for b in buys if b.get("id") != a["id"]]
            if len(keep) != len(buys):
                removed += 1
                rec = dict(rec, purchases=keep, qty=len(keep))
                collection_put(a["sid"], a["n"], rec)
        last["undone"] = now_iso()
        st["lastSync"] = last
        write_json(SETTINGS, st)
    log(f"Undid the last phone sync: removed {removed} purchase(s).")
    return {"removed": removed}


def list_auto_backups():
    """Backups saved on the server, newest first: [{name, kind, created, size}]."""
    out = []
    for f in os.listdir(BACKUPS) if os.path.isdir(BACKUPS) else []:
        m = AUTO_NAME_RE.fullmatch(f)
        if m:
            path = os.path.join(BACKUPS, f)
            out.append({"name": f, "kind": backup_kind(m.group(1)), "size": os.path.getsize(path),
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
        with big_job("a restore"):
            return _restore_from(z, names)


def _restore_from(z, names):
    """Write a checked backup over the binder's data (restore_backup does the checks)."""
    safety = auto_backup("before-restore")
    with lock:
        with tx():   # all of the data goes in together, or none of it does
            for n in names:
                if DOC_RE.fullmatch(n):
                    db_write(n, json.loads(z.read(n)))
        for sid in {n.split("/")[1] for n in names if n.startswith("sets/")}:
            shutil.rmtree(sdir(sid, "photos"), ignore_errors=True)
        if "favicon" not in names:
            for f in ("favicon", "favicon.json"):
                if os.path.exists(os.path.join(DATA, f)):
                    os.remove(os.path.join(DATA, f))
        for n in names:
            if DOC_RE.fullmatch(n):
                continue
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
            if not data_exists(sdir(sid, "history.json")):
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

# Which web addresses the binder answers to. IP addresses, localhost, one-word names (like "myserver") and
# home/Tailscale names always work. Add others, like a reverse proxy name, in BINDER_HOSTS (comma separated).
# This blocks "DNS rebinding", where an outside website points its own name at your binder.
EXTRA_HOSTS = {h.strip().lower() for h in os.environ.get("BINDER_HOSTS", "").split(",") if h.strip()}
LOCAL_SUFFIXES = (".local", ".lan", ".home", ".home.arpa", ".internal", ".ts.net")


OTHER_HOSTS = set()   # extra addresses from Settings > Server > Other addresses (kept in step with settings.json)


def load_other_hosts():
    global OTHER_HOSTS
    try:
        OTHER_HOSTS = {h.lower() for h in (get_settings().get("otherHosts") or []) if isinstance(h, str)}
    except Exception:
        OTHER_HOSTS = set()


def clean_hosts(raw):
    """Settings > Server > Other addresses: names like binder.example.com or 203.0.113.5:8765, one per item."""
    items = raw if isinstance(raw, list) else re.split(r"[\s,]+", str(raw or ""))
    out = []
    for h in items:
        h = str(h).strip().lower()
        h = re.sub(r"^[a-z]+://", "", h).split("/")[0]   # people paste whole web addresses
        if not h:
            continue
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?)*(?::\d{1,5})?", h):
            raise ValueError(f"\"{h}\" doesn't look like a web address. Use a name like binder.example.com")
        if h not in out:
            out.append(h)
    if len(out) > 10:
        raise ValueError("Up to 10 other addresses")
    return out


def host_ok(host_header):
    h = (host_header or "").strip().lower()
    if h in OTHER_HOSTS:
        return True
    if h.startswith("["):                       # IPv6 like [::1]:8765
        return True
    name = h.rsplit(":", 1)[0] if h.count(":") == 1 else h
    if not name or name in EXTRA_HOSTS or name in OTHER_HOSTS or name == "localhost" or "." not in name:
        return True
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", name):
        return True
    return name.endswith(LOCAL_SUFFIXES)

# Text replies are squeezed with gzip before sending (every browser unpacks it): the page and binder data
# get about 4 times smaller, which matters most on a phone over Tailscale. Pictures are already compressed.
COMPRESSIBLE = {"application/json", "text/html", "text/plain", "text/csv", "image/svg+xml", "application/javascript", "text/css"}
_gz_cache = {}


def gzipped(body, etag=None):
    """gzip `body`; files with an ETag (the page, the fonts) are squeezed once and remembered."""
    if etag and etag in _gz_cache:
        return _gz_cache[etag]
    out = gzip.compress(body, 6)
    if etag:
        if len(_gz_cache) >= 8:
            _gz_cache.clear()
        _gz_cache[etag] = out
    return out


class Handler(BaseHTTPRequestHandler):
    # A device that connects and then goes quiet (a phone losing signal mid-load) is let go after a minute,
    # so it can't tie up part of the server for good. Only silence counts: slow uploads keep going.
    timeout = 60

    def log_message(self, fmt, *args):
        pass

    def send_response(self, code, message=None):
        self.replied = True
        super().send_response(code, message)

    def end_headers(self):
        # browsers must use the type we say (never guess a file is a web page)
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def send(self, code, body=b"", ctype="application/json", cache=None, etag=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        if etag and code == 200 and self.headers.get("If-None-Match") == etag:
            self.send_response(304)   # the browser already has this exact file
            self.send_header("ETag", etag)
            if cache:
                self.send_header("Cache-Control", cache)
            self.end_headers()
            return
        squeeze = ctype.split(";")[0].strip() in COMPRESSIBLE and len(body) > 1024
        if squeeze and "gzip" in (self.headers.get("Accept-Encoding") or "").lower():
            body = gzipped(body, etag)
        else:
            squeeze = False
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if squeeze:
            self.send_header("Content-Encoding", "gzip")
        if ctype.split(";")[0].strip() in COMPRESSIBLE:
            self.send_header("Vary", "Accept-Encoding")
        if cache:
            self.send_header("Cache-Control", cache)
        if etag:
            self.send_header("ETag", etag)
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, ctype, cache="max-age=604800"):
        try:
            st = os.stat(path)
            etag = f'"{st.st_mtime_ns:x}-{st.st_size:x}"'
            if self.headers.get("If-None-Match") == etag:
                return self.send(200, b"", ctype, cache, etag)
            with open(path, "rb") as f:
                self.send(200, f.read(), ctype, cache, etag)
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
        if path == "/manifest.webmanifest":   # lets Chrome install the binder as an app
            custom = os.path.exists(ICON_FILE) and read_json(ICON_FILE + ".json", {}).get("type") == "image/png"
            icons = ([{"src": "app-icon.png?v=" + str(int(os.path.getmtime(ICON_FILE))), "sizes": "512x512", "type": "image/png", "purpose": "any"}]
                     if custom else
                     [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                      {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}])
            man = {"name": "Pokémon Binder", "short_name": "Binder", "id": "./", "start_url": "./", "scope": "./",
                   "display": "standalone", "background_color": "#111213", "theme_color": "#111213", "icons": icons}
            return self.send(200, json.dumps(man).encode(), "application/manifest+json", "no-cache")
        if path == "/sw.js":   # the version goes in, so each binder update refreshes the phone's saved copies
            try:
                with open(os.path.join(APP, "sw.js"), "rb") as f:
                    body = f.read().replace(b"__VERSION__", APP_VERSION.encode())
            except OSError:
                return self.send(404, b"not found", "text/plain")
            return self.send(200, body, "application/javascript; charset=utf-8", "no-cache")
        if path in ("/icon-192.png", "/icon-512.png"):
            return self.send_file(os.path.join(APP, path[1:]), "image/png")
        if path == "/app-icon.png":   # your own tab icon from Settings, used as the app icon too
            return self.send_file(ICON_FILE, "image/png", "no-cache")
        if path == "/fonts.css":   # fonts kept on the server; the page asks for fonts.css?v=<n>, so a new version means a new address
            return self.send_file(os.path.join(APP, "fonts.css"), "text/css; charset=utf-8", "max-age=31536000, immutable")
        m = re.fullmatch(r"/art/(\d{1,4})(s?)\.png", path)
        if m:
            try:
                return self.send_file(pokemon_art(m.group(1), m.group(2) == "s"), "image/png")
            except Exception as e:
                log(f"Pokémon art {m.group(1)}{m.group(2)}: {e}")
                return self.send(404, b"not found", "text/plain")
        m = re.fullmatch(r"/unown/([a-z])\.png", path)
        if m:
            try:
                return self.send_file(unown_sprite(m.group(1)), "image/png")
            except Exception as e:
                log(f"Unown {m.group(1)}: {e}")
                return self.send(404, b"not found", "text/plain")
        if path in ("/favicon", "/favicon.ico"):
            if os.path.exists(ICON_FILE):
                return self.send_file(ICON_FILE, read_json(ICON_FILE + ".json", {}).get("type", "image/png"), "no-cache")
            return self.send(200, DEFAULT_ICON, "image/svg+xml", "no-cache")
        if path == "/api/icon":
            return self.send(200, {"custom": os.path.exists(ICON_FILE)}, cache="no-store")
        if path == "/api/backups":
            return self.send(200, {"backups": list_auto_backups()}, cache="no-store")
        if path == "/api/export.xlsx":   # every binder in one spreadsheet
            body = export_collection()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="pokemon-binder-{time.strftime("%Y-%m-%d")}.xlsx"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
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
                return self.send(404, {"error": f"That backup isn't on {srv_name()} any more"})
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
        if path == "/api/health":
            h = health()
            return self.send(200 if h["ok"] else 503, h, cache="no-store")
        if path == "/api/status":
            return self.send(200, status(), cache="no-store")
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
                size = binder_size(sid)
                m["count"] = size if size is not None else m.get("total", 0) + m["custom"]
                m["images"] = sid in img_jobs
                if size is not None:
                    have, want = pictures_saved(sid, (cards or []) + extra_list(sid))
                    m["pics"] = {"saved": have, "total": want}
                    m["totals"] = set_totals(sid)
                out.append(m)
            return self.send(200, {"sets": out, "removed": removed_sets(), "keepDays": KEEP_REMOVED_DAYS}, cache="no-store")
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
            keep = shows_keep_from()   # between weekly scans, shows older than yesterday drop off the list each day
            return self.send(200, {"shows": sorted((tidy_show(x) for x in st["shows"].values() if x["date"] >= keep),
                                                   key=lambda s: (s["date"], s["name"])),
                                   "areas": st["areas"], "auto": st["auto"], "scanned": st.get("scanned", ""),
                                   "firstScan": st.get("firstScan", ""), "error": st.get("error", ""), "running": shows_job["running"],
                                   "done": shows_job["done"], "total": shows_job["total"],
                                   "today": today_local()}, cache="no-store")
        if path == "/api/changelog":
            return self.send(200, changelog(), cache="no-store")
        if path == "/api/progress":
            # everything the server is working on, for the loading bars
            imgs = {sid: dict(v) for sid, v in list(img_jobs.items()) if isinstance(v, dict)}
            return self.send(200, {"prices": job, "images": imgs, "pokedex": dex_job, "shows": shows_job},
                             cache="no-store")
        if path == "/api/catalog":
            return self.send(200, {"sets": catalog()}, cache="no-store")
        if path == "/api/find":
            q = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("q") or [""])[0]
            return self.send(200, find(q[:120]), cache="no-store")
        m = re.fullmatch(rf"/api/find/set/({SID_RE})", path)
        if m:
            try:
                return self.send(200, find_set(m.group(1)), cache="no-store")
            except ValueError as e:
                return self.send(404, {"error": str(e)})
        if path == "/api/refresh":
            return self.send(200, job, cache="no-store")
        if path == "/api/settings":
            st = get_settings()
            out = {k: st[k] for k in ("auto", "time", "tz", "slots")}
            out["backup"] = bool(st.get("backup", True))
            out["serverName"] = (st.get("serverName") or "").strip()
            out["otherHosts"] = list(st.get("otherHosts") or [])
            ls = st.get("lastSync") or {}
            out["lastSync"] = {"at": ls.get("at", ""), "count": len(ls.get("added") or []), "undone": ls.get("undone", "")} if ls else None
            out["refreshAll"] = bool(st.get("refreshAll"))
            out["showBinders"] = list(st.get("showBinders") or [])
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
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            card = (q.get("card") or [""])[0]
            if card:   # one card's chart
                if not re.fullmatch(NUM_RE, card):
                    return self.send(400, {"error": "bad card"})
                return self.send(200, {"card": card, "points": card_series(m.group(1), card)}, cache="no-store")
            return self.send(200, read_json(sdir(m.group(1), "history.json"), {}), cache="no-store")
        m = re.fullmatch(rf"/api/set/({SID_RE})/trends", path)
        if m:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            today = (q.get("today") or [""])[0]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", today):
                today = today_local()
            try:
                return self.send(200, set_trends(m.group(1), today), cache="no-store")
            except ValueError:
                return self.send(400, {"error": "bad date"})
        if path == "/api/show":
            return self.send(200, show_data(), cache="no-store")
        if path == "/api/home":
            return self.send(200, home_data(), cache="no-store")
        if path == "/api/covernums":   # Pokédex numbers for the binder covers: ?c=neo4-1,neo4-107
            q = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("c") or [""])[0]
            gids = [g for g in q.split(",") if re.fullmatch(NUM_RE, g)]
            return self.send(200, {"dex": card_dex(gids)})
        m = re.fullmatch(rf"/api/set/({SID_RE})/dexnums", path)
        if m:   # Pokédex numbers for a binder's cards, for the Pages view's "Pokédex number" order
            sid = m.group(1)
            if not self.in_binder(sid):
                return self.send(404, {"error": "Set not in binder"})
            idx = card_index()
            if not idx:
                return self.send(200, {"ready": False, "dex": {}}, cache="no-store")
            multi, out = is_multi(sid), {}
            for c in set_cards(sid):
                if c.get("custom"):
                    continue
                row = idx["by"].get(c["n"] if (multi or c.get("extra")) else f"{sid}-{c['n']}")
                if row and len(row) > 7 and row[7]:
                    out[c["n"]] = row[7]
            return self.send(200, {"ready": True, "dex": out}, cache="no-store")
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
                        "shop": read_json(sdir(sid, "shop.json"), {}),
                        "layout": read_json(sdir(sid, "layout.json"), None)}
            return self.send(200, body, cache="no-store")
        m = re.fullmatch(rf"/set/({SID_RE})/logo\.png", path)
        if m:
            got = set_logo(m.group(1))
            if not got:
                return self.send(404, b"not found", "text/plain")
            return self.send_file(got, "image/png")
        m = re.fullmatch(rf"/set/({SID_RE})/sprite\.png", path)
        if m:
            return self.send_file(sdir(m.group(1), "sprite.png"), "image/png")
        m = re.fullmatch(rf"/set/({SID_RE})/img/({NUM_RE})\.png", path)
        if m:
            full = "full=1" in (self.path.split("?") + [""])[1]
            got = card_image(m.group(1), m.group(2), full) if (self.in_binder(m.group(1)) or os.path.isdir(sdir(m.group(1)))) else None
            if not got:
                return self.send(404, b"not found", "text/plain")
            return self.send_file(got, "image/png")
        m = re.fullmatch(rf"/set/({SID_RE})/photo/({NUM_RE})(?:/(back))?", path)
        if m:
            name = m.group(2) + ("_back" if m.group(3) else "")
            meta = read_json(sdir(m.group(1), "photos", name + ".json"), {})
            ctype = meta.get("type", "image/jpeg")
            return self.send_file(sdir(m.group(1), "photos", name), ctype if ctype in PHOTO_TYPES else "application/octet-stream", "no-cache")
        self.send(404, b"not found", "text/plain")

    def do_PUT(self):
        if self.blocked(True):
            return
        if self.path == "/api/settings":
            return self.do_PUT_settings()
        if self.path == "/api/shows":
            return self.do_PUT_shows()
        if self.path == "/api/sets/order":
            return self.do_PUT_set_order()
        m = re.fullmatch(rf"/api/sets/({SID_RE})/name", self.path)
        if m:
            try:
                return self.send(200, rename_own(m.group(1), json.loads(self.body(4096) or b"{}").get("name")))
            except (ValueError, AttributeError) as e:
                return self.send(400, {"error": str(e) or "Couldn't rename"})
        m = re.fullmatch(rf"/api/set/({SID_RE})/layout", self.path)
        if m:
            if not self.in_binder(m.group(1)):
                return self.send(400, {"error": "That binder isn't here"})
            try:
                raw = json.loads(self.body(256 * 1024) or b"{}")
                assert isinstance(raw, dict)
                return self.send(200, save_layout(m.group(1), raw))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            except Exception:
                return self.send(400, {"error": "Couldn't save the layout"})
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
            collection_put(sid, n, rec)
        self.send(200, {"ok": True})

    def do_PUT_shows(self):
        """Card show options: the towns to look in and whether to scan every week."""
        try:
            new = json.loads(self.body(4096) or b"{}")
            assert isinstance(new, dict)
            if "areas" in new:
                areas = [str(a).strip() for a in new["areas"] if str(a).strip()]
                assert 1 <= len(areas) <= 40 and all(len(a) <= 40 and re.fullmatch(r"[A-Za-z .'\-]+", a) for a in areas)
        except Exception:
            return self.send(400, {"error": "Use town names separated by commas, like Richmond, Midlothian"})
        with lock:   # read and save together, so a scan finishing at the same moment can't undo this
            st = shows_state()
            if "auto" in new:
                st["auto"] = bool(new["auto"])
            if "areas" in new:
                st["areas"] = list(dict.fromkeys(areas))
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

    def do_PUT_set_order(self):
        """Save the order of binders in the sets menu. Must list exactly the binders you have."""
        try:
            new = json.loads(self.body(16 * 1024) or b"{}").get("order")
            assert isinstance(new, list) and all(isinstance(x, str) for x in new)
        except Exception:
            return self.send(400, {"error": "Invalid order"})
        with lock:
            sl = sets_list()
            if sorted(new) != sorted(sl["order"]) or len(set(new)) != len(new):
                return self.send(409, {"error": "Your binders changed. Reload and try again"})
            sl["order"] = new
            write_json(SETS_FILE, sl)
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
            assert isinstance(new, dict)
            # read and save together, so the scheduler saving "last run" at the same moment can't undo this
            with lock:
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
                if "refreshAll" in new:
                    st["refreshAll"] = bool(new["refreshAll"])
                if "serverName" in new:
                    name = re.sub(r"\s+", " ", str(new["serverName"] or "")).strip()
                    if len(name) > 24 or not re.fullmatch(r"[\w .'\-]*", name):
                        raise ValueError("Use letters, numbers, spaces, dots or dashes for the server name (24 at most)")
                    st["serverName"] = name
                if "otherHosts" in new:
                    st["otherHosts"] = clean_hosts(new["otherHosts"])
                if "showBinders" in new:   # card show mode: the binders you're working on
                    order = sets_list()["order"]
                    st["showBinders"] = [x for x in dict.fromkeys(new["showBinders"] or []) if isinstance(x, str) and x in order]
                # a new time today shouldn't be skipped just because today's run already happened earlier
                if "time" in new:
                    merged = dict(DEFAULT_SETTINGS); merged.update(st)
                    now = local_now(merged)
                    h, m = map(int, merged["time"].split(":"))
                    if now < now.replace(hour=h, minute=m, second=0, microsecond=0):
                        st["lastAuto"] = ""
                write_json(SETTINGS, st)
        except Exception as e:
            return self.send(400, {"error": str(e) if isinstance(e, ValueError) and str(e) else "Invalid settings"})
        merged = get_settings()
        load_other_hosts()
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
        m = re.fullmatch(rf"/api/set/({SID_RE})/cards/({NUM_RE})", self.path)
        if m:
            if not self.in_binder(m.group(1)):
                return self.send(400, {"error": "That binder isn't here"})
            try:
                remove_card(m.group(1), m.group(2))
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
        if path == "/api/sync":   # the phone app sends what was added while offline
            try:
                new = json.loads(self.body(256 * 1024) or b"{}")
                assert isinstance(new, dict) and isinstance(new.get("changes"), list) and len(new["changes"]) <= 500
            except Exception:
                return self.send(400, {"error": "Invalid sync"})
            try:
                return self.send(200, dict(apply_sync(new["changes"]), ok=True))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        if path == "/api/sync/undo":
            try:
                return self.send(200, dict(undo_sync(), ok=True))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
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
            except Busy as e:
                return self.send(409, {"error": str(e)})
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
                return self.send(400, {"error": f"That backup isn't on {srv_name()} any more"})
            try:
                count, safety = restore_backup(os.path.join(BACKUPS, name))
            except Busy as e:
                return self.send(409, {"error": str(e)})
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
        m_pic = re.fullmatch(rf"/api/sets/({SID_RE})/pictures", path)
        if m_pic:
            if m_pic.group(1) not in sets_list()["order"]:
                return self.send(404, {"error": "No such binder"})
            start_images(m_pic.group(1), now=True)
            return self.send(200, {"started": True})
        m_buy = re.fullmatch(rf"/api/set/({SID_RE})/card/({NUM_RE})/buy", path)
        if m_buy:   # card show mode: add one copy you just bought, from any screen
            try:
                body = json.loads(self.body(4096) or b"{}")
                assert isinstance(body, dict)
                sid, n, purchase = clean_sync_change({"sid": m_buy.group(1), "n": m_buy.group(2),
                                                      "purchase": body.get("purchase"), "cond": body.get("cond")})
                if sid not in sets_list()["order"]:
                    raise ValueError("That binder isn't on the server any more")
                with lock:
                    added = add_one_purchase(sid, n, purchase)
            except (ValueError, AssertionError) as e:
                return self.send(400, {"error": str(e) or "bad request"})
            except Exception:
                return self.send(400, {"error": "bad request"})
            return self.send(200, {"ok": True, "added": added})
        m_rs = re.fullmatch(rf"/api/sets/({SID_RE})/restore", path)
        if m_rs:
            try:
                return self.send(200, restore_set(m_rs.group(1)))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        if path == "/api/sets/own":
            try:
                return self.send(200, add_own(json.loads(self.body(4096) or b"{}").get("name")))
            except (ValueError, AttributeError) as e:
                return self.send(400, {"error": str(e) or "Couldn't make the binder"})
        m_add = re.fullmatch(rf"/api/set/({SID_RE})/cards", path)
        if m_add:
            sid = m_add.group(1)
            if not self.in_binder(sid):
                return self.send(400, {"error": "That binder isn't here"})
            try:
                gid = json.loads(self.body(4096) or b"{}").get("id", "")
                assert isinstance(gid, str) and re.fullmatch(NUM_RE, gid)
            except Exception:
                return self.send(400, {"error": "bad request"})
            try:
                return self.send(200, add_card(sid, gid))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        if path == "/api/sets":
            raw = self.body(4096)
            try:
                body = json.loads(raw or b"{}")
                sid, keep = body.get("id", ""), body.get("keep")
                assert re.fullmatch(SID_RE, sid) and keep in (None, True, False)
                meta = add_set_again(sid, keep)
            except SavedCards as e:
                return self.send(409, {"error": str(e), "saved": e.saved})
            except urllib.error.URLError as e:
                return self.send(502, {"error": f"Couldn't download the card list: {e}"})
            except Exception as e:
                return self.send(400, {"error": str(e) or "Couldn't add that set"})
            return self.send(200, meta)
        if path == "/api/update":
            # install the latest version (from GitHub, or the updates folder)
            if not GH_REPO and not os.path.isdir(UPDATES):
                return self.send(400, {"error": "Updates aren't set up"})
            try:
                with big_job("an update") as slot:
                    installed = install_from_github() if GH_REPO else install_files(UPDATES, "update from the updates folder")
                    restarting = any(n.endswith(".py") for n in installed)
                    slot["keep"] = restarting   # keep other big jobs out until the binder restarts on the new version
            except Busy as e:
                return self.send(409, {"error": str(e)})
            except Exception as e:
                return self.send(502, {"error": gh_error(e)})
            self.send(200, {"installed": installed, "restarting": restarting})
            if restarting:
                threading.Thread(target=restart_self, args=(1,), daemon=True).start()
            return
        if path == "/api/rollback":
            raw = self.body(4096)
            try:
                vid = json.loads(raw or b"{}").get("id", "")
                with big_job("a rollback") as slot:
                    installed = rollback(vid)
                    restarting = any(n.endswith(".py") for n in installed)
                    slot["keep"] = restarting
            except Busy as e:
                return self.send(409, {"error": str(e)})
            except Exception as e:
                return self.send(400, {"error": str(e) or "Couldn't roll back"})
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
            try:
                sid = str(json.loads(raw or b"{}").get("set", ""))
            except Exception:
                return self.send(400, {"error": "bad request"})
            if not job["running"] and sid and self.in_binder(sid):
                threading.Thread(target=refresh_prices, args=(sid, "manual"), daemon=True).start()
                time.sleep(0.2)
            return self.send(200, job)
        m = re.fullmatch(rf"/api/set/({SID_RE})/photo/({NUM_RE})(?:/(back))?", path)
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if not m or not self.in_binder(m.group(1)):
            return self.send(400, {"error": "bad request"})
        if ctype not in PHOTO_TYPES:
            return self.send(400, {"error": "Use a JPG, PNG, WebP, GIF or HEIC photo"})
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


def _safe(fn):
    """Any unexpected error in a request still gets an answer (instead of the page waiting on nothing),
    and the details go to the container log."""
    def run(self):
        self.replied = False
        try:
            return fn(self)
        except (BrokenPipeError, ConnectionResetError):
            pass   # the browser went away
        except Exception as e:
            log(f"{self.command} {self.path} failed:\n{traceback.format_exc().rstrip()}")
            if not self.replied:
                try:
                    self.send(500, {"error": f"Something went wrong on {srv_name()} ({e.__class__.__name__}). The container log has details"})
                except OSError:
                    pass
    return run


for _name in ("do_GET", "do_PUT", "do_POST", "do_DELETE"):
    setattr(Handler, _name, _safe(getattr(Handler, _name)))


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
# The program files of THIS version. The updater reads this line from a new server.py to know what to download,
# so a later version can be split into more files. Versions before v3.0 only ever had these two.
APP_FILES = ("server.py", "index.html", "fonts.css", "sw.js", "icon-192.png", "icon-512.png")
UPDATE_FILES = APP_FILES
APP_FILE_RE = re.compile(r"[A-Za-z0-9_\-]+(?:/[A-Za-z0-9_\-]+)*\.(?:py|html|js|css|woff2|png|svg|json|txt)")
GH_REPO = os.environ.get("GITHUB_REPO", "g-i-n-g-y/pokemon-binder")
GH_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
VERSION_FILE = os.path.join(APP, ".version.json")   # {commit, subject, date, installed, paused}
PREVIOUS = os.path.join(APP, "previous")            # previous/<stamp>/{server.py, index.html, meta.json}
KEEP_VERSIONS = 3
update_status = {"source": "", "checked": "", "error": ""}


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def files_of(server_path):
    """The program files the server.py at `server_path` needs (its APP_FILES line), safest names only.
    Versions from before v3.0 have no such line and use server.py and index.html."""
    try:
        with open(server_path, encoding="utf-8", errors="ignore") as f:
            m = re.search(r"^APP_FILES\s*=\s*(\([^)]*\))", f.read(), re.M)
        names = tuple(ast.literal_eval(m.group(1))) if m else ("server.py", "index.html")
    except (OSError, ValueError, SyntaxError):
        names = ("server.py", "index.html")
    if "server.py" not in names or not all(isinstance(n, str) and APP_FILE_RE.fullmatch(n) for n in names):
        raise RuntimeError("The new version's file list looks wrong, so nothing was installed")
    return names


def copy_into(src_root, dst_root, names):
    for name in names:
        dst = os.path.join(dst_root, *name.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(src_root, *name.split("/")), dst)


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


def trial_run(folder):
    """Start the new version on a spare port, with a copy of your data, and check that its pages answer.
    Nothing it does touches the real binder. Returns "" if it works, or what went wrong."""
    with open(os.path.join(folder, "server.py"), encoding="utf-8", errors="ignore") as f:
        if "BINDER_TRIAL" not in f.read():
            return ""   # versions from before v2.20 can't be test-started; the syntax check still ran
    tmp = tempfile.mkdtemp(prefix=".trial-", dir=APP)
    proc = logf = None
    try:
        copy_into(folder, tmp, files_of(os.path.join(folder, "server.py")))
        # a copy of the small data files only (no card pictures or photos)
        for root, dirs, files in os.walk(DATA):
            dirs[:] = [d for d in dirs if d not in ("images", "photos") and not d.startswith("pre-sqlite")]
            for fn in files:
                if fn.endswith(".json"):
                    dst = os.path.join(tmp, "data", os.path.relpath(os.path.join(root, fn), DATA))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copyfile(os.path.join(root, fn), dst)
        if os.path.exists(DB_FILE):   # a consistent copy of the database, made while the binder keeps running
            os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
            dst = sqlite3.connect(os.path.join(tmp, "data", "binder.db"))
            try:
                with db_lock:
                    db().backup(dst)
            finally:
                dst.close()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        logf = open(os.path.join(tmp, "trial.log"), "w+")
        proc = subprocess.Popen([sys.executable, "-u", os.path.join(tmp, "server.py")], cwd=tmp, stdout=logf,
                                stderr=subprocess.STDOUT, env=dict(os.environ, BINDER_PORT=str(port), BINDER_TRIAL="1"))
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        order = sets_list()["order"]
        pages = ["/", "/api/sets", "/api/settings", "/api/version", "/api/spending", "/api/changelog"] + \
                [f"/api/set/{sid}/state" for sid in order[:3]]

        def status(page):
            try:
                with opener.open(f"http://127.0.0.1:{port}{page}", timeout=15) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                return e.code

        deadline = time.time() + 25
        while True:   # wait for it to start
            if proc.poll() is not None:
                break
            try:
                status("/")
                break
            except (urllib.error.URLError, OSError):
                if time.time() > deadline:
                    break
                time.sleep(0.5)
        problem = ""
        if proc.poll() is not None:
            problem = "it stopped right after starting"
        else:
            for page in pages:
                try:
                    code = status(page)
                except Exception as e:
                    problem = f"{page} didn't answer ({e.__class__.__name__})"
                    break
                if code >= 500 and code != 502:   # 502 = a website it needs is down, not a problem with the app
                    problem = f"{page} gave error {code}"
                    break
        if problem:
            logf.seek(0)
            tail = [ln for ln in logf.read().splitlines() if ln.strip()][-8:]
            log("Update test failed: " + problem + ("\n  " + "\n  ".join(tail) if tail else ""))
        return problem
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if logf:
            logf.close()
        shutil.rmtree(tmp, ignore_errors=True)


def save_current_version():
    """Keep a copy of the running version so it can be rolled back to later (newest 3 are kept)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    dest = os.path.join(PREVIOUS, stamp)
    os.makedirs(dest, exist_ok=False)
    copy_into(APP, dest, [n for n in APP_FILES if os.path.isfile(os.path.join(APP, *n.split("/")))])
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
    if not os.path.isfile(os.path.join(folder, "server.py")):
        return []
    names = files_of(os.path.join(folder, "server.py"))
    missing = [n for n in names if not os.path.isfile(os.path.join(folder, *n.split("/")))]
    if missing:
        raise RuntimeError(f"The new version is missing {', '.join(missing)}, so nothing was installed")
    changed = [n for n in names if not same_file(os.path.join(folder, *n.split("/")), os.path.join(APP, *n.split("/")))]
    if not changed:
        return []
    # skip the whole update if the new version is broken, so you keep a working binder
    broken = [n for n in names if n.endswith(".py") and not server_ok(os.path.join(folder, *n.split("/")))]
    if broken:
        raise RuntimeError("The new version has a mistake in its code, so nothing was installed. You're still on the current version")
    problem = trial_run(folder)
    if problem:
        raise RuntimeError(f"The new version failed a test start ({problem}), so nothing was installed. "
                           "You're still on the current version")
    try:
        auto_backup("before-update")
    except Exception as e:
        log(f"Update skipped: couldn't save a backup first ({e})")
        raise RuntimeError(f"Update skipped because a backup couldn't be saved first: {e}")
    save_current_version()
    # copy everything next to its place first, then swap them in, server.py last
    for name in changed:
        dst = os.path.join(APP, *name.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(folder, *name.split("/")), dst + ".tmp")
    for name in sorted(changed, key=lambda n: n == "server.py"):
        dst = os.path.join(APP, *name.split("/"))
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
    if isinstance(e, RuntimeError):   # our own message, like "the new version didn't start"
        return str(e)
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
    """Download this version's program files at `sha` (default: latest) and install them. Returns files installed."""
    update_status.update(source="github", checked=now_iso(), error="")
    info = commit_info(gh_json(f"commits/{sha or GH_BRANCH}"))
    stage = os.path.join(APP, ".incoming")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage, exist_ok=True)

    def fetch(name):
        dst = os.path.join(stage, *name.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(gh_get(f"contents/{name}?ref={info['sha']}", "application/vnd.github.raw"))

    fetch("server.py")   # first: it says which other files this version needs
    for name in files_of(os.path.join(stage, "server.py")):
        if name != "server.py":
            fetch(name)
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
    with open(os.path.join(folder, "server.py"), encoding="utf-8", errors="ignore") as f:
        uses_db = "DB_FILE" in f.read()
    # versions before v3.0 keep data in JSON files: write today's data out for them first
    exported = [] if uses_db else export_to_files()
    try:
        installed = install_files(folder, f"rollback to {meta.get('commit', '')[:7] or 'older version'}")
    except Exception:
        for k in exported:
            try:
                os.remove(os.path.join(DATA, *k.split("/")))
            except OSError:
                pass
        raise
    if exported and installed:
        retire_db()
        log("Rolled back to a version without the database. Your data was written out as JSON files for it; "
            "binder.db was renamed, not deleted.")
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
    try:
        os.execv(sys.executable, [sys.executable, "-u", os.path.abspath(__file__)])
    except OSError as e:   # very unlikely; don't leave updates blocked until the container restarts
        log(f"Couldn't restart ({e}). Restart the container to finish the update.")
        with job_lock:
            big["what"] = ""


def version_info():
    out = {}
    for name in APP_FILES:
        try:
            out[name] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(os.path.join(APP, name))))
        except OSError:
            out[name] = ""
    cur = current_version()
    size = sum(os.path.getsize(DB_FILE + ext) for ext in ("", "-wal") if os.path.exists(DB_FILE + ext))
    out["storage"] = {"kind": "database", "file": "data/binder.db", "size": size}
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
    load_other_hosts()
    if TRIAL:   # an update test start: answer pages only (no downloads, no schedule), and only on this machine
        def _no_downloads(*args, **kwargs):
            raise urllib.error.URLError("no downloads during an update test")
        urllib.request.urlopen = _no_downloads
        log(f"Pokemon Binder test start on port {PORT}")
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    safely("cleaning up leftover files", clean_leftovers)
    threading.Thread(target=warm_up, daemon=True).start()
    threading.Thread(target=scheduler, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()
    log(f"Pokemon Binder running on port {PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
