"""Price history, purchases and spending, the daily price check, first start.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

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


COND_ORDER = ("NM", "LP", "MP", "HP", "DMG")


def snapshot_cond_history(sid, prices=None):
    """For the card page's chart: save today's average price for each condition of every card, and keep every
    recent sale the server has seen (TCGplayer only shows the newest 5 per condition, so the log grows over time).
    cond_history.json is {day: {card: [NM, LP, MP, HP, DMG]}} with only the cards whose numbers changed since their
    last saved day, so it stays small. sales_log.json is {card: {condition: [[day, price], ...]}}, oldest first."""
    prices = prices if prices is not None else read_json(sdir(sid, "prices.json"), {})
    info = (prices or {}).get("info") or {}
    if not isinstance(info, dict) or not info:
        return
    today = today_local()
    hist = read_json(sdir(sid, "cond_history.json"), {})
    hist = hist if isinstance(hist, dict) else {}
    last = {}   # each card's numbers as of the day before today
    for d in sorted(hist):
        if d < today and isinstance(hist[d], dict):
            last.update(hist[d])
    row = dict(hist.get(today) or {})
    sales = read_json(sdir(sid, "sales_log.json"), {})
    sales = sales if isinstance(sales, dict) else {}
    sales_changed = False
    for n, inf in info.items():
        if not isinstance(inf, dict):
            continue
        cond = inf.get("cond") if isinstance(inf.get("cond"), dict) else {}
        vals = [round(cond[c][0], 2) if isinstance(cond.get(c), list) and cond[c] and _is_num(cond[c][0]) else None
                for c in COND_ORDER]
        if any(v is not None for v in vals) and last.get(n) != vals:
            row[n] = vals
        else:
            row.pop(n, None)
        for c, got in (inf.get("recent") if isinstance(inf.get("recent"), dict) else {}).items():
            if c not in COND_ORDER or not isinstance(got, list):
                continue
            have = sales.setdefault(n, {}).setdefault(c, [])
            seen = {(d, p) for d, p in have}
            for s in got:
                ok = isinstance(s, list) and len(s) == 2 and isinstance(s[0], str) and _is_num(s[1])
                if ok and (s[0][:10], round(s[1], 2)) not in seen:
                    have.append([s[0][:10], round(s[1], 2)])
                    seen.add((s[0][:10], round(s[1], 2)))
                    sales_changed = True
            have.sort()
    if row != (hist.get(today) or {}):
        if row:
            hist[today] = row
        else:
            hist.pop(today, None)
        write_json(sdir(sid, "cond_history.json"), hist)
    if sales_changed:
        write_json(sdir(sid, "sales_log.json"), sales)


def card_cond_series(sid, n):
    """One card's chart lines by condition: {"NM": [[day, price], ...], ...}, only the days the price changed."""
    hist = read_json(sdir(sid, "cond_history.json"), {})
    out = {c: [] for c in COND_ORDER}
    for d in sorted(hist if isinstance(hist, dict) else {}):
        vals = hist[d].get(n) if isinstance(hist[d], dict) else None
        if isinstance(vals, list):
            for c, v in zip(COND_ORDER, vals):
                if _is_num(v):
                    out[c].append([d, v])
    return {c: pts for c, pts in out.items() if pts}


def card_sales(sid, n):
    """Every sale saved for one card: {"NM": [[day, price], ...], ...}, oldest first."""
    sales = read_json(sdir(sid, "sales_log.json"), {})
    got = sales.get(n) if isinstance(sales, dict) else None
    return {c: got[c] for c in COND_ORDER if isinstance(got, dict) and got.get(c)}


TREND_DAYS = (1, 7, 30, 90, 365)   # the price change periods the page offers (plus "all time")


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def set_trends(sid, today):
    """Everything the page needs to show price changes, without sending every saved day:
    for each card, its first and last saved price, how many days have one, and the price as it stood
    1, 7, 30, 90 and 365 days before `today`. Stays the same size however long history grows."""
    base = datetime.strptime(today, "%Y-%m-%d").date()
    cuts = [(str(p), (base - timedelta(days=p)).isoformat()) for p in TREND_DAYS]
    since90 = (base - timedelta(days=90)).isoformat()
    hist = read_json(sdir(sid, "history.json"), {})
    hist = hist if isinstance(hist, dict) else {}
    cards, first, last90 = {}, "", {}
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
            if since90 <= d <= today:
                last90.setdefault(n, []).append((d, v))
    # for the vendor price check: the lowest and middle (median) saved price over the last 90 days,
    # how many days that is, and the first of those days
    for n, pts in last90.items():
        vals = sorted(v for _, v in pts)
        m = len(vals) // 2
        med = vals[m] if len(vals) % 2 else (vals[m - 1] + vals[m]) / 2
        cards[n]["h90"] = [round(vals[0], 2), round(med, 2), len(vals), pts[0][0]]
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
        cards = {c["n"]: c["name"] for c in (card_list(sid) or []) + extra_list(sid)}
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
            "backupSize": sum(b["size"] for b in backups), "backupCount": len(backups),
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
    safely("leftover temporary files", clean_leftovers, 6 * 3600)   # anything temporary older than 6 hours
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
