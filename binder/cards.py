"""Card lists: the set catalog, added and custom cards, Pokémon master sets, Find a card, your own binders, page layouts.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

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


# Rarities the card database leaves out, by card id: holos without a rarity symbol, checked against TCGdex and
# TCGplayer. Southern Islands: six of its 18 cards are reverse holos. McDonald's 2011–2019: every card is a holo.
# Trainer kits: one holo each. Dragon Vault: every card is a holo, but three were left blank.
RARITY_FIXES = {
    **{f"si1-{n}": "Reverse Holo" for n in (1, 4, 7, 11, 14, 17)},
    **{f"mcd{y}-{n}": "Holo" for y in (11, 12, 14, 15, 16, 17, 18, 19) for n in range(1, 13)},
    **{n: "Holo" for n in ("tk1a-4", "tk1b-2", "tk2a-6", "tk2b-6")},
    **{n: "Rare Holo" for n in ("dv1-18", "dv1-19", "dv1-21")},
}


def fix_rarity(cards, sid=""):
    """Put the right rarity on cards from the card database, including card lists saved before a fix was added."""
    for c in cards or []:
        n = str(c.get("n", ""))
        fix = RARITY_FIXES.get(n if "-" in n else f"{sid}-{n}")
        if fix:
            c["rarity"] = fix
    return cards


def card_list(sid):
    """A binder's saved card list (None if it isn't saved yet)."""
    return fix_rarity(read_json(sdir(sid, "cards.json"), None), sid)


def fetch_cards(sid):
    raw = json.loads(http_get(f"{GH}/cards/en/{sid}.json"))
    cards = []
    for c in raw:
        cards.append({"n": str(c["number"]), "name": c["name"], "rarity": c.get("rarity") or "",
                      "type": c.get("supertype", ""),
                      "img": (c.get("images") or {}).get("large") or (c.get("images") or {}).get("small", "")})
    cards.sort(key=lambda c: num_key(c["n"]))
    fix_rarity(cards, sid)
    write_json(sdir(sid, "cards.json"), cards)
    return cards


def set_cards(sid):
    """Every card in a binder: the card database's list, cards you added from Find a card, and custom cards."""
    cards = card_list(sid)
    if cards is None:
        cards = [] if is_own(sid) else dex_cards(sid) if is_dex(sid) else fetch_cards(sid)
    return cards + extra_list(sid) + custom_cards(sid)


def binder_size(sid):
    """How many cards a binder holds, without downloading anything. None if its card list isn't saved yet."""
    cards = card_list(sid)
    if cards is None and not is_own(sid):
        return None
    return len(cards or []) + len(extra_list(sid)) + len(custom_list(sid))


# ---------- cards added from Find a card ----------
# Saved per binder in extra.json, each remembering its own set, like the cards in a master set binder.
# Their number is the card database's id (like neo1-80), so it never clashes with a set's own numbers.
# Your own binders ("my-1") hold only these.

def extra_list(sid):
    out = read_json(sdir(sid, "extra.json"), [])
    return fix_rarity([c for c in out if isinstance(c, dict) and re.fullmatch(NUM_RE, str(c.get("n", "")))]) if isinstance(out, list) else []


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
            if local and any(c["n"] == local for c in (card_list(sid) or [])):
                return {"n": local, "already": True}
        elif is_dex(sid) and any(c["n"] == gid for c in (card_list(sid) or [])):
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
                every.append([n, c["name"], str(c["number"]), RARITY_FIXES.get(n) or c.get("rarity") or "", c.get("supertype", ""),
                              (c.get("images") or {}).get("large") or (c.get("images") or {}).get("small", ""), st["id"],
                              ((c.get("nationalPokedexNumbers") or [0])[0] or 0)])
                if c.get("supertype") != "Pokémon":
                    continue
                card = {"n": n, "num": str(c["number"]), "set": st["name"], "pt": st.get("printedTotal", 0),
                        "date": st.get("releaseDate", ""), "name": c["name"], "rarity": RARITY_FIXES.get(n) or c.get("rarity") or "",
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
    return {"n": c[0], "name": c[1], "num": c[2], "rarity": RARITY_FIXES.get(c[0]) or c[3], "type": c[4], "img": c[5],
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
        base = card_list(sid) or []
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
        cards = card_list(sid)
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


def all_sellers(limit=60):
    """Everyone you've bought from, across every binder: [{p, h, n (purchases), last (date)}], most recent first."""
    seen = {}
    for sid in sets_list()["order"]:
        coll = read_json(sdir(sid, "collection.json"), {})
        for r in coll.values() if isinstance(coll, dict) else []:
            for b in (r.get("purchases") or []) if isinstance(r, dict) else []:
                sel = b.get("seller") if isinstance(b, dict) else None
                if not (isinstance(sel, dict) and isinstance(sel.get("h"), str) and sel["h"].strip()):
                    continue
                p, h = str(sel.get("p") or "shop")[:20], sel["h"].strip()[:100]
                k = (p, h.lower())
                e = seen.setdefault(k, {"p": p, "h": h, "n": 0, "last": ""})
                e["n"] += 1
                d = str(b.get("d") or "")
                if d >= e["last"]:
                    e["last"], e["h"], e["p"] = d, h, p   # the name as written on your newest purchase from them
    return sorted(seen.values(), key=lambda e: (e["last"], e["n"]), reverse=True)[:limit]


OFFER_SPLIT = 20   # vendor price check: "cheap" cards are under this, the rest are holos and chase cards


def _median(vals):
    s = sorted(vals)
    if not s:
        return 0
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def pay_habit():
    """How much you usually pay compared with a card's price, from every purchase with a price, in every binder.
    {"cheap": {"r": 1.6, "n": 12}, "dear": {...}}: r is the middle paid/price ratio, n how many purchases.
    Cheap = cards priced under OFFER_SPLIT. Uses each card's price today, so it's a rough guide."""
    out = {"cheap": [], "dear": []}
    for sid in sets_list()["order"]:
        coll = read_json(sdir(sid, "collection.json"), {})
        prices = (read_json(sdir(sid, "prices.json"), {}) or {}).get("p") or {}
        for n, r in (coll.items() if isinstance(coll, dict) else []):
            mkt = (prices.get(n) or [0])[0] or 0
            if not isinstance(r, dict) or not _is_num(mkt) or mkt <= 0:
                continue
            for b in r.get("purchases") or []:
                paid = b.get("price") if isinstance(b, dict) else None
                if _is_num(paid) and paid > 0:
                    out["cheap" if mkt < OFFER_SPLIT else "dear"].append(paid / mkt)
    return {k: {"r": round(_median(v), 3), "n": len(v)} for k, v in out.items() if v}


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
        cards = card_list(sid)
        cards = (cards or []) + extra_list(sid) + custom_cards(sid) if cards is not None or is_own(sid) else []
        pr = read_json(sdir(sid, "prices.json"), {}) or {}
        prices, info = pr.get("p") or {}, pr.get("info") or {}
        # where each card sits in the binder's pages: your arranged pockets if you've moved cards, else set order
        # (the phone refines this with the exact order it last showed for the binder)
        lay = read_json(sdir(sid, "layout.json"), {}) or {}
        pk = lay.get("pockets") if lay.get("pockets") in POCKETS else 9
        slot = {}
        if isinstance(lay.get("slots"), list):
            slot = {x: i for i, x in enumerate(lay["slots"]) if isinstance(x, str)}
        nxt = (max(slot.values()) + 1) if slot else 0
        for c in cards:
            if c["n"] not in slot:
                slot[c["n"]] = nxt
                nxt += 1
        need = 0
        try:
            tr = set_trends(sid, today)["cards"]   # for the vendor price check's 30-day change
        except Exception:
            tr = {}
        for c in cards:
            if _owned(coll.get(c["n"])):
                continue
            need += 1
            i = info.get(c["n"]) or {}
            t = tr.get(c["n"]) or {}
            was = (t.get("at", {}).get("30") or t.get("first") or [None, 0])[1]
            now = (prices.get(c["n"]) or [0])[0] or 0
            t30 = round((now - was) / was * 100, 1) if _is_num(was) and was and now and t.get("count", 0) >= 2 else None
            was7 = (t.get("at", {}).get("7") or t.get("first") or [None, 0])[1]
            t7 = round((now - was7) / was7 * 100, 1) if _is_num(was7) and was7 and now and t.get("count", 0) >= 2 else None
            cards_out.append({"sid": sid, "set": meta.get("name", sid), "n": c["n"], "name": c.get("name", ""),
                              "num": c.get("num", c["n"]),
                              "pt": c.get("pt") or ("" if is_multi(sid) or c.get("extra") or c.get("custom") else meta.get("printedTotal") or ""), "rarity": c.get("rarity", ""),
                              "custom": bool(c.get("custom")), "price": (prices.get(c["n"]) or [0])[0] or 0,
                              "src": i.get("src", ""), "last": i.get("last", ""), "slot": slot.get(c["n"], 0),
                              "cond": i.get("cond") or {}, "recent": i.get("recent") or {}, "t30": t30, "t7": t7,
                              "h90": t.get("h90")})
        binders.append({"id": sid, "name": meta.get("name", sid), "need": need, "pk": pk})
    return {"picked": picked, "binders": binders, "cards": cards_out, "today": today,
            "bought": bought, "spent": round(spent, 2), "sellers": all_sellers(), "habit": pay_habit()}
