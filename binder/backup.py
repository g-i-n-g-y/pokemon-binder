"""Backups and restore.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

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


SECRET_SETTINGS = ("psaToken",)   # kept out of backups, so a backup file is safe to keep anywhere


def make_backup(target, photos=True):
    """A zip of your data as JSON files (the same layout every version uses), plus the tab icon and (unless
    photos=False) your card photos. backup.json says whether photos are in it, so restoring one without them
    leaves your current photos alone."""
    with lock:
        with db_lock:   # one consistent moment: nothing can save while this reads
            docs = [(k, db_read(k)) for k in db_keys() if BACKUP_RE.fullmatch(k)]
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("backup.json", json.dumps({"app": "pokemon-binder", "version": APP_VERSION, "created": now_iso(),
                                                  "photos": bool(photos)}))
            for k, obj in docs:
                if k == "settings.json" and isinstance(obj, dict):
                    obj = {s: v for s, v in obj.items() if s not in SECRET_SETTINGS}
                z.writestr(k, json.dumps(obj, indent=1))
            for name in backup_files():
                if photos or "/photos/" not in name:
                    z.write(os.path.join(DATA, name), name)


PHOTO_KINDS = ("before-restore", "before-fresh")   # these can remove photos, so their backups keep them
WEEK = 7 * DAY


def backup_photos(kind):
    """Should this automatic backup include your photos? Photos never change during an update, phone sync or
    spreadsheet import, so those backups skip them (each copy of every photo adds up fast). Restores and fresh
    starts keep them, and one daily backup a week does."""
    if kind in PHOTO_KINDS:
        return True
    if kind == "daily":
        return time.time() - (get_settings().get("photoBackupAt") or 0) > WEEK - 3600
    return False


def auto_backup(kind):
    """Save a backup of all binder data in backups/ on the server before something that changes it a lot
    (an update, a spreadsheet import, a restore). Keeps the newest few of each kind. Returns the file name."""
    os.makedirs(BACKUPS, exist_ok=True)
    name = f"{kind}-{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}.zip"
    tmp = os.path.join(BACKUPS, name + ".tmp")
    photos = backup_photos(kind)
    try:
        make_backup(tmp, photos=photos)
        os.replace(tmp, os.path.join(BACKUPS, name))
        if photos and kind == "daily":
            with lock:
                st = read_json(SETTINGS, {})
                st["photoBackupAt"] = int(time.time())
                write_json(SETTINGS, st)
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
