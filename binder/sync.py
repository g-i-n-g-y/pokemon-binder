"""Phone app: changes made offline, and sending them with Sync.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

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
            try:
                with zipfile.ZipFile(path) as z:
                    photos = json.loads(z.read("backup.json")).get("photos", True) is not False
            except Exception:
                photos = True
            out.append({"name": f, "kind": backup_kind(m.group(1)), "size": os.path.getsize(path), "photos": photos,
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
                    obj = json.loads(z.read(n))
                    if n == "settings.json" and isinstance(obj, dict):   # backups leave out the PSA key: keep yours
                        now = db_read("settings.json")
                        obj.update({s: now[s] for s in SECRET_SETTINGS if isinstance(now, dict) and s in now and s not in obj})
                    db_write(n, obj)
        try:
            has_photos = json.loads(z.read("backup.json")).get("photos", True) is not False
        except Exception:
            has_photos = True
        if has_photos:   # a backup made without photos (an automatic one) leaves your current photos as they are
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
            if not data_exists(sdir(sid, "sales_log.json")) or not data_exists(sdir(sid, "market_history.json")):   # first start with the chart: begin with what's saved
                with lock:
                    snapshot_cond_history(sid)
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
