"""PSA slab check.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

# ---------- PSA slab check ----------
# Looks up a PSA cert number with PSA's free public service (needs your own access code from psacard.com/publicapi,
# saved in Settings > Prices). PSA allows about 100 lookups a day, so each slab is looked up once and kept in
# data/psa/ (the newest PSA_KEEP slabs). That folder is a cache: it isn't backed up and can be deleted any time.
PSA_API = os.environ.get("PSA_API") or "https://api.psacard.com/publicapi"   # PSA_API is only for testing
PSA_DIR = os.path.join(DATA, "psa")
PSA_FILE = os.path.join(PSA_DIR, "checks.json")
PSA_KEEP = 60
psa_lock = threading.Lock()


class PsaError(Exception):
    def __init__(self, msg, code=502):
        super().__init__(msg)
        self.code = code


def psa_call(path):
    tok = (get_settings().get("psaToken") or "").strip()
    if not tok:
        raise PsaError("Add your PSA access code in Settings → Prices first.", 400)
    # a plain app name, not a browser's: PSA's firewall can turn away requests that claim to be a browser but aren't
    req = urllib.request.Request(PSA_API + path, headers={"Authorization": "bearer " + tok, "Accept": "application/json",
                                                          "User-Agent": f"PokemonBinder/{APP_VERSION}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        try:
            snip = e.read(400).decode("utf-8", "replace")
        except Exception:
            snip = ""
        short = re.sub(r"\s+", " ", snip)[:200]
        log(f"PSA slab check failed: error {e.code}: {short}")
        html = bool(re.search(r"<html|cloudflare|just a moment|attention required", snip, re.I))
        if e.code == 429:
            raise PsaError("PSA's daily limit is used up (error 429). Try again tomorrow.", 429)
        if html and e.code in (403, 503):
            raise PsaError(f"PSA's website turned away the server's request (error {e.code}). That's PSA's firewall, not your code.", 502)
        if e.code == 403 and "approved customers" in snip:
            raise PsaError("PSA only lets approved customers use its lookup service (error 403).", 502)
        if e.code in (401, 403):
            raise PsaError(f"PSA says the access code isn't valid (error {e.code}). Copy it again from psacard.com/publicapi into Settings → Prices.", 502)
        if e.code == 500:   # PSA's docs: a 500 usually means a wrong or expired access code
            raise PsaError("PSA didn't accept the access code (error 500). Copy it again from psacard.com/publicapi into Settings → Prices.", 502)
        raise PsaError(f"PSA's lookup isn't answering right now (error {e.code}). Try again in a bit.")
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        log(f"PSA slab check failed: couldn't reach PSA: {e}")
        raise PsaError("Couldn't reach PSA from the server. Check the server's internet and try again.")
    if not body.strip():
        return {}
    try:
        return json.loads(body)
    except ValueError:
        raise PsaError("PSA sent back something unexpected. Try again in a bit.")


def psa_grade(text):
    """'NM-MT 8' -> ('8', 'NM-MT'); 'GEM MT 10' -> ('10', 'GEM MT'); 'AUTHENTIC' -> ('', 'AUTHENTIC')."""
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    m = re.search(r"(\d{1,2}(?:\.5)?)\b", t)
    if not m:
        return "", t
    return m.group(1), (t[:m.start()] + t[m.end():]).strip(" -")


def psa_images(cert):
    out = {}
    try:
        j = psa_call(f"/cert/GetImagesByCertNumber/{cert}")
    except PsaError:
        return out
    items = j if isinstance(j, list) else next((v for v in j.values() if isinstance(v, list)), []) if isinstance(j, dict) else []
    for it in items:
        if isinstance(it, dict) and str(it.get("ImageURL") or "").startswith("https://"):
            out["front" if it.get("IsFrontImage") else "back"] = it["ImageURL"]
    return out


PSA_WEB = os.environ.get("PSA_WEB") or "https://www.psacard.com"   # PSA_WEB is only for testing
psa_state = {"denied": 0}   # when PSA last said the access code isn't approved (it's asked again a day later)


def psa_entry(cert, f, imgs, source):
    num, words = psa_grade(f.get("grade"))
    def count(v):
        m = re.search(r"\d[\d,]*", str(v if v is not None else ""))
        return int(m.group(0).replace(",", "")) if m else None
    return {"cert": cert, "grade": num, "gradeText": words or str(f.get("grade") or ""), "desc": str(f.get("grade") or ""),
            "year": str(f.get("year") or ""), "brand": str(f.get("brand") or ""), "subject": str(f.get("subject") or ""),
            "num": str(f.get("num") or "").lstrip("#"), "variety": str(f.get("variety") or ""), "category": str(f.get("category") or ""),
            "pop": count(f.get("pop")), "higher": count(f.get("higher")), "dna": False,
            "imgs": imgs, "source": source, "at": now_iso()}


def psa_api_lookup(cert):
    j = psa_call(f"/cert/GetByCertNumber/{cert}")
    c = j.get("PSACert") if isinstance(j, dict) else None
    if not isinstance(c, dict) or not (c.get("CertNumber") or c.get("Subject")):
        return None
    f = {"grade": c.get("CardGrade") or c.get("GradeDescription"), "year": c.get("Year"), "brand": c.get("Brand"),
         "subject": c.get("Subject"), "num": c.get("CardNumber"), "variety": c.get("Variety"), "category": c.get("Category"),
         "pop": c.get("TotalPopulation"), "higher": c.get("PopulationHigher")}
    return psa_entry(cert, f, psa_images(cert), "api")


# Reading PSA's public cert page (the one anyone can open). Its layout isn't documented, so this tries the
# page's built-in data first, then its visible "label / value" text.
PSA_JSON_KEYS = {"grade": ("CardGrade", "GradeDescription", "ItemGrade", "cardGrade", "gradeDescription", "itemGrade"),
                 "year": ("Year", "year"), "brand": ("Brand", "brand", "BrandTitle", "brandTitle"),
                 "subject": ("Subject", "subject"), "num": ("CardNumber", "cardNumber"),
                 "variety": ("Variety", "variety", "VarietyPedigree", "varietyPedigree"), "category": ("Category", "category"),
                 "pop": ("TotalPopulation", "totalPopulation", "Population", "population"),
                 "higher": ("PopulationHigher", "populationHigher", "PopHigher", "popHigher")}
PSA_LABELS = {"item grade": "grade", "grade": "grade", "card grade": "grade", "year": "year", "brand/title": "brand",
              "brand": "brand", "subject": "subject", "card number": "num", "card #": "num", "category": "category",
              "variety/pedigree": "variety", "variety": "variety", "population": "pop", "psa population": "pop",
              "pop higher": "higher", "pop. higher": "higher", "population higher": "higher"}


def _psa_from_json(html):
    for text in (html, html.replace('\\"', '"')):
        if not re.search(r'"(?:Cert|cert)Number"', text):
            continue
        f = {}
        for field, keys in PSA_JSON_KEYS.items():
            for k in keys:
                m = re.search(r'"' + k + r'"\s*:\s*("(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?)', text)
                if m:
                    try:
                        v = json.loads(m.group(1))
                    except ValueError:
                        v = m.group(1).strip('"')
                    if v not in ("", None):
                        f[field] = v
                        break
        if f.get("subject") and f.get("grade"):
            return f
    return None


def _psa_lines(html):
    t = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", html)
    t = re.sub(r"(?s)<[^>]+>", "\n", t)
    return [x for x in (re.sub(r"\s+", " ", unescape(line)).strip() for line in t.split("\n")) if x]


def _psa_from_text(lines):
    f = {}
    for i, line in enumerate(lines[:-1]):
        field = PSA_LABELS.get(line.lower().rstrip(":").strip())
        nxt = lines[i + 1]
        if field and field not in f and nxt.lower().rstrip(":") not in PSA_LABELS and len(nxt) < 120:
            f[field] = nxt
    return f if f.get("subject") and f.get("grade") else None


def _psa_page_imgs(html):
    urls = []
    for u in re.findall(r'https://[^"\'\s<>()]+?\.(?:jpe?g|png|webp)(?:\?[^"\'\s<>()]*)?', html.replace("\\/", "/"), re.I):
        if re.search(r"logo|icon|sprite|badge|avatar|placeholder|banner", u, re.I) or u in urls:
            continue
        if re.search(r"cloudfront|cert|/images?/", u, re.I):
            urls.append(u)
    return {k: v for k, v in zip(("front", "back"), urls[:2])}


def psa_page_lookup(cert):
    """PSA's public cert page. Returns the details, None when PSA says there's no such cert, or "blocked"."""
    req = urllib.request.Request(f"{PSA_WEB}/cert/{cert}/psa", headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read(4_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        log(f"PSA slab check failed: PSA's cert page answered with error {e.code}")
        return "blocked"
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        log(f"PSA slab check failed: couldn't reach PSA's cert page: {e}")
        return "blocked"
    f = _psa_from_json(html)
    lines = _psa_lines(html)
    f = f or _psa_from_text(lines)
    if f:
        return psa_entry(cert, f, _psa_page_imgs(html), "page")
    text = " ".join(lines)
    if re.search(r"not a valid cert|no record|could not be found|cert(?:ification)? (?:number )?not found|invalid cert", text, re.I):
        return None
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    blocked = re.search(r"just a moment|attention required|cf-chl|captcha|access denied", html, re.I)
    why = "blocked by its firewall" if blocked else "layout not recognized"
    ttl = re.sub(r"\s+", " ", title.group(1)).strip()[:80] if title else "none"
    log(f"PSA slab check failed: couldn't read PSA's cert page ({why}; title: {ttl})")
    return "blocked"


def psa_lookup(cert):
    """PSA's lookup service when your access code is approved, otherwise PSA's public cert page.
    Returns the details, None for no such cert, or {"manual": True} when neither could be read."""
    tok = (get_settings().get("psaToken") or "").strip()
    if tok and time.time() - psa_state["denied"] > 86400:
        try:
            return psa_api_lookup(cert)
        except PsaError as e:
            if "approved customers" in str(e):
                psa_state["denied"] = time.time()
    e = psa_page_lookup(cert)
    return {"manual": True, "cert": cert} if e == "blocked" else e


PSA_SKIP = {"holo", "rev", "reverse", "foil", "1st", "edition", "ed", "shadowless", "pokemon", "card", "game"}


def _psa_words(t):
    return set(re.findall(r"[a-z0-9]+", _fold(t))) - PSA_SKIP


def psa_match(e):
    """The card in your binders that this slab is: same card number, every word of the card's name in PSA's
    description, and the binder's set name in PSA's set name when it can tell. None when nothing matches."""
    num = _num_fold(e.get("num"))
    if not num:
        return None
    subj, brand = _psa_words(e.get("subject")), _psa_words(e.get("brand"))
    sl = sets_list()
    best, best_score = None, 0
    for sid in sl["order"]:
        meta = sl["meta"].get(sid, {})
        cards = card_list(sid)
        cards = (cards or []) + extra_list(sid) + custom_cards(sid) if cards is not None or is_own(sid) else []
        set_words = _psa_words(meta.get("name", ""))
        for c in cards:
            if _num_fold(c.get("num", c["n"])) != num:
                continue
            nm = _psa_words(c.get("name", ""))
            if not nm or not nm <= subj:
                continue
            cset = _psa_words(c["set"]) if c.get("set") else set_words
            score = 2 + (1 if cset and cset <= brand else 0)
            if score > best_score:
                best, best_score = (sid, meta, c, cards), score
    if not best:
        return None
    sid, meta, c, cards = best
    coll = read_json(sdir(sid, "collection.json"), {})
    rec = coll.get(c["n"]) if isinstance(coll.get(c["n"]), dict) else {}
    pr = read_json(sdir(sid, "prices.json"), {}) or {}
    info = (pr.get("info") or {}).get(c["n"]) or {}
    lay = read_json(sdir(sid, "layout.json"), {}) or {}
    pk = lay.get("pockets") if lay.get("pockets") in POCKETS else 9
    order = [x for x in lay["slots"] if isinstance(x, str)] if isinstance(lay.get("slots"), list) else []
    order += [x["n"] for x in cards if x["n"] not in order]
    page = order.index(c["n"]) // pk + 1 if c["n"] in order else 0
    return {"sid": sid, "set": c.get("set") or meta.get("name", sid), "binder": meta.get("name", sid), "n": c["n"],
            "name": c.get("name", ""), "cardNum": c.get("num", c["n"]),
            "pt": c.get("pt") or ("" if is_multi(sid) or c.get("custom") else meta.get("printedTotal") or ""),
            "rarity": c.get("rarity", ""), "year": str(c.get("date") or meta.get("releaseDate") or "")[:4],
            "owned": _owned(rec), "price": ((pr.get("p") or {}).get(c["n"]) or [0])[0] or 0,
            "pc": info.get("pc", ""), "tcg": c.get("tcg", ""), "page": page, "sure": best_score == 3}


def psa_check(cert):
    if not re.fullmatch(r"\d{5,12}", cert or ""):
        raise PsaError("A PSA cert number is 5 to 12 digits.", 400)
    with psa_lock:
        cache = read_file_json(PSA_FILE, {})
    e = cache.get(cert) if isinstance(cache, dict) else None
    if not isinstance(e, dict):
        e = psa_lookup(cert)
        if not e:
            return {"found": False, "cert": cert}
        if e.get("manual"):
            return {"found": None, "manual": True, "cert": cert}
        with psa_lock:
            cache = read_file_json(PSA_FILE, {})
            cache = cache if isinstance(cache, dict) else {}
            cache[cert] = e
            keep = sorted(cache, key=lambda k: cache[k].get("at", ""), reverse=True)[:PSA_KEEP]
            for k in set(cache) - set(keep):   # forget the oldest slabs and their pictures
                for side in ("front", "back"):
                    with contextlib.suppress(OSError):
                        os.remove(os.path.join(PSA_DIR, f"{k}-{side}.jpg"))
            os.makedirs(PSA_DIR, exist_ok=True)
            write_file_json(PSA_FILE, {k: cache[k] for k in keep})
    out = dict(e)
    out["imgs"] = sorted((e.get("imgs") or {}).keys())
    out["found"] = True
    try:
        out["match"] = psa_match(e)
    except Exception as ex:
        log(f"PSA {cert}: matching to your binders failed: {ex}")
        out["match"] = None
    return out


def psa_picture(cert, side):
    """PSA's own photo of the slab, saved in data/psa the first time it's shown."""
    path = os.path.join(PSA_DIR, f"{cert}-{side}.jpg")
    if not os.path.isfile(path):
        with psa_lock:
            e = (read_file_json(PSA_FILE, {}) or {}).get(cert) or {}
        url = (e.get("imgs") or {}).get(side)
        if not url:
            return None
        _download(url, path)
    return path


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
