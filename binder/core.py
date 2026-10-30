"""Locks and big jobs, small helpers, and storage: your data in data/binder.db.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

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
             "extra", "layout", "cond_history", "sales_log")
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
