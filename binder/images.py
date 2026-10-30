"""Card pictures, set logos and Pokémon art.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

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


# Card pictures only come from these websites, so a card list from an edited backup can't send the server elsewhere.
PICTURE_SITES = ("https://images.pokemontcg.io/", "https://images.scrydex.com/")


def fetch_image(sid, card, full=False):
    """Make sure one card picture is on the server. Returns its path, or None."""
    n = card["n"]
    dest = image_path(sid, n, full)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    url = card.get("img") or ""
    if not url.startswith(PICTURE_SITES):
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
