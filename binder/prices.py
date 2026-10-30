"""Prices: TCGplayer sales, price slots, PriceCharting graded prices, TCGdex market prices.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

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
        link = re.search(r'href="(https?://(?:www\.)?ebay\.com/itm/[^"\s]+)"', row)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row)).strip()
        m = re.match(r"(\d{4}-\d{2}-\d{2}|[A-Z][a-z]{2,8}\.? \d{1,2},? \d{4})\s+(.*?)\s+\$([\d,]+\.\d{2})\b", text)
        if m:
            d = m.group(1)
            if not d[0].isdigit():
                try:
                    d = datetime.strptime(d.replace(".", "").replace(",", "")[:3] + " " + " ".join(d.replace(",", "").split()[1:]), "%b %d %Y").strftime("%Y-%m-%d")
                except ValueError:
                    continue
            out.append({"d": d, "title": m.group(2), "price": float(m.group(3).replace(",", "")),
                        "url": unescape(link.group(1)).split("?")[0] if link else ""})
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
                lst.append([x["d"], x["price"], x.get("url", "")])   # the eBay listing, when PriceCharting links it
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
                job["message"] = f"{name} was removed during the price check."
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
        job["message"] = f"Price check failed: {e}"
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
