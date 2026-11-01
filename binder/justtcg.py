"""JustTCG prices: the key, the request limits, and backup prices for cards with no recent sales.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

# ---------- JustTCG ----------
# JustTCG is a card price service that needs your own key (free plan: 100 requests a day, 1,000 a month).
# The key comes from the JUSTTCG_API_KEY environment variable (Unraid: a Docker variable with Password Mask on)
# or from Settings > Prices. It never leaves the server: the page is only told where it's set, backups leave it
# out, it's only ever sent to JustTCG, and log() blanks it out of every log line.
JUSTTCG_API = "https://api.justtcg.com/v1"
_jt_test = os.environ.get("JUSTTCG_API", "")   # only for testing, and only to this computer
if re.fullmatch(r"http://(127\.0\.0\.1|localhost):\d{1,5}(/[\w/]*)?", _jt_test):
    JUSTTCG_API = _jt_test.rstrip("/")
JT_KEY_RE = r"[\w\-.]{8,200}"
SECRETS.add(os.environ.get("JUSTTCG_API_KEY", "").strip())
jt_usage = {}   # the newest "requests left" numbers JustTCG sent, for Settings > Prices
# The free plan allows 1,000 requests a month, so the binder keeps its own count and stops at the limits in
# Settings > Prices (default 600 a month, 25 a day), and always leaves JT_RESERVE of the month's requests unused.
JT_COUNT = os.path.join(DATA, "justtcg_count.json")   # {"month", "monthUsed", "day", "dayUsed"}; not backed up
JT_RESERVE = 100
JT_MODES = ("off", "refresh", "nightly")   # per binder: never, when you tap Refresh prices, also in the nightly check
JT_BATCH = 20   # cards per request on the free plan
JT_AGAIN = 7    # days before the same card is asked about again
JT_STALE = 14   # days after which a JustTCG price is too old to use
jt_lock = threading.Lock()


class JustTcgError(Exception):
    def __init__(self, msg, code=502):
        super().__init__(msg)
        self.code = code


def justtcg_key():
    """(key, where) with where "docker" (the environment variable), "settings" or ""."""
    env = os.environ.get("JUSTTCG_API_KEY", "").strip()
    if env:
        SECRETS.add(env)
        return env, "docker"
    key = (get_settings().get("justtcgKey") or "").strip()
    if key:
        SECRETS.add(key)
        return key, "settings"
    return "", ""


def justtcg_call(path, body=None):
    """One JustTCG request with the key (a GET, or a POST of `body` as JSON). Counts it toward the binder's
    limits and keeps the "requests left" numbers JustTCG answers with."""
    key, _ = justtcg_key()
    if not key:
        raise JustTcgError("Add your JustTCG key first.", 400)
    headers = {"x-api-key": key, "Accept": "application/json", "User-Agent": f"PokemonBinder/{APP_VERSION}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(JUSTTCG_API + path, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    jt_count_one()
    opener = urllib.request.build_opener(_NoRedirect)   # a redirect would carry the key to another address
    try:
        with opener.open(req, timeout=30) as r:
            body = json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read(2000) or b"{}")
        except Exception:
            body = {}
        why = hide_secrets(str(body.get("error") or body.get("message") or ""))[:200]
        log(f"JustTCG: error {e.code}{': ' + why if why else ''}")
        if isinstance(body, dict):
            justtcg_keep_usage(body)
        if e.code in (401, 403):
            raise JustTcgError(f"JustTCG didn't accept the key (error {e.code}). Copy it again from your JustTCG dashboard.")
        if e.code == 429:
            raise JustTcgError("JustTCG's request limit is used up for now (error 429). Try again later.", 429)
        if 300 <= e.code < 400:
            raise JustTcgError(f"JustTCG sent the request somewhere else (error {e.code}), so it wasn't followed.")
        raise JustTcgError(f"JustTCG isn't answering right now (error {e.code}). Try again in a bit.")
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
        log(f"JustTCG: couldn't reach it: {hide_secrets(str(e))[:200]}")
        raise JustTcgError("Couldn't reach JustTCG from the server. Check the server's internet and try again.")
    justtcg_keep_usage(body)
    return body


def justtcg_keep_usage(body):
    u = (body.get("_metadata") or body.get("usage")) if isinstance(body, dict) else None
    if not isinstance(u, dict):
        return
    nums = {k: u[k] for k in ("apiDailyLimit", "apiDailyRequestsRemaining", "apiRequestLimit", "apiRequestsRemaining",
                              "apiRateLimit") if _is_num(u.get(k))}
    if nums:
        jt_usage.clear()
        jt_usage.update(nums, plan=str(u.get("apiPlan") or "")[:40], at=now_iso())


def jt_counts():
    """This month's and today's requests by the binder (a new month or day starts again at 0)."""
    today = today_local()
    c = read_file_json(JT_COUNT, {})
    c = c if isinstance(c, dict) else {}
    month = c.get("monthUsed", 0) if c.get("month") == today[:7] and _is_num(c.get("monthUsed")) else 0
    day = c.get("dayUsed", 0) if c.get("day") == today and _is_num(c.get("dayUsed")) else 0
    return {"month": today[:7], "monthUsed": int(month), "day": today, "dayUsed": int(day)}


def jt_count_one():
    with jt_lock:
        c = jt_counts()
        c["monthUsed"] += 1
        c["dayUsed"] += 1
        write_file_json(JT_COUNT, c)


def jt_limits(st=None):
    st = st or get_settings()
    month, day = st.get("jtMonth"), st.get("jtDay")
    return (int(month) if _is_num(month) else 600), (int(day) if _is_num(day) else 25)


def justtcg_left():
    """How many more requests the binder may make right now: its own limits, and never JustTCG's last JT_RESERVE."""
    month_cap, day_cap = jt_limits()
    c = jt_counts()
    left = min(month_cap - c["monthUsed"], day_cap - c["dayUsed"])
    if _is_num(jt_usage.get("apiRequestsRemaining")):
        left = min(left, jt_usage["apiRequestsRemaining"] - JT_RESERVE)
    if _is_num(jt_usage.get("apiDailyRequestsRemaining")):
        left = min(left, jt_usage["apiDailyRequestsRemaining"] - 5)
    return max(0, int(left))


def jt_mode(sid):
    m = (get_settings().get("jtBinders") or {}).get(sid)
    return m if m in JT_MODES else "off"


def justtcg_status():
    """For Settings > Prices: where the key is set (never the key), the newest requests-left numbers, what the
    binder has used against its limits, and the binders that use JustTCG."""
    _, where = justtcg_key()
    month_cap, day_cap = jt_limits()
    c = jt_counts()
    modes = {sid: jt_mode(sid) for sid in sets_list()["order"]}
    return {"key": where, "usage": dict(jt_usage) if where else None,
            "used": {"month": c["monthUsed"], "day": c["dayUsed"]}, "limits": {"month": month_cap, "day": day_cap},
            "reserve": JT_RESERVE, "binders": {sid: m for sid, m in modes.items() if m != "off"}}


def justtcg_check():
    """Try the key with JustTCG's smallest request (the list of games). Uses one request."""
    justtcg_call("/games")
    return justtcg_status()


# ---------- backup prices ----------

JT_COND = {"Near Mint": "NM", "Lightly Played": "LP", "Moderately Played": "MP", "Heavily Played": "HP", "Damaged": "DMG"}


def jt_variants(card, rarity=""):
    """The JustTCG variants for the binder's kind of copy: English, not 1st Edition, holo or not like the card."""
    holo = "holo" in (rarity or "").lower() and "reverse" not in (rarity or "").lower()
    variants = [v for v in (card or {}).get("variants") or [] if isinstance(v, dict)
                and "1st" not in str(v.get("printing")) and v.get("language") in (None, "", "English")]
    printings = {str(v.get("printing") or "") for v in variants}
    if len(printings) > 1:   # more than one kind: holo (not reverse) for a holo card, the plain one otherwise
        variants = [v for v in variants if ("holo" in str(v.get("printing")).lower()
                                            and "reverse" not in str(v.get("printing")).lower()) == holo]
    return variants


def jt_prices(card, rarity=""):
    """{"NM": [price, "YYYY-MM-DD"], ...} from one JustTCG card, leaving out prices older than JT_STALE days."""
    out, now = {}, time.time()
    for v in jt_variants(card, rarity):
        short, at = JT_COND.get(v.get("condition")), v.get("lastUpdated")
        if short and short not in out and _is_num(v.get("price")) and v["price"] > 0 and _is_num(at) and now - at < JT_STALE * DAY:
            out[short] = [round(v["price"], 2), time.strftime("%Y-%m-%d", time.gmtime(at))]
    return out


def jt_backup_prices(sid, wanted):
    """Ask JustTCG about cards with no recent sales, 20 to a request, within the binder's request limits.
    wanted is {card: (TCGplayer id, rarity)}. Returns {card: {"jt": prices, "jtAt": day}} for the cards it got to."""
    today, got, asked = today_local(), {}, 0
    items = list(wanted.items())
    for i in range(0, len(items), JT_BATCH):
        if justtcg_left() <= 0:
            log(f"{sid}: JustTCG request limit reached; {len(items) - i} cards wait for another day")
            break
        if asked:
            time.sleep(7)   # the free plan allows 10 requests a minute
        chunk = items[i:i + JT_BATCH]
        try:
            ans = justtcg_call("/cards", [{"tcgplayerId": str(pid)} for _, (pid, _) in chunk])
        except JustTcgError as e:
            log(f"{sid}: JustTCG: {e}")
            break
        asked += 1
        by_id = {str(c.get("tcgplayerId")): c for c in ans.get("data") or [] if isinstance(c, dict)}
        for n, (pid, rarity) in chunk:
            got[n] = {"jt": jt_prices(by_id.get(str(pid)), rarity), "jtAt": today}
    if asked:
        log(f"{sid}: JustTCG priced {sum(1 for g in got.values() if g['jt'])} of {len(got)} cards with no recent sales "
            f"({asked} request{'s' if asked != 1 else ''})")
    return got


def jt_wanted(sid, reason, fresh, slots, cards, pids):
    """The cards this price check should ask JustTCG about: only in a binder that uses it for this kind of check,
    only cards with no recent sales for the binder's price options, and each card at most once every JT_AGAIN days."""
    mode = jt_mode(sid)
    if mode == "off" or (mode == "refresh" and reason == "scheduled") or not justtcg_key()[0]:
        return {}
    soon = (datetime.strptime(today_local(), "%Y-%m-%d") - timedelta(days=JT_AGAIN)).strftime("%Y-%m-%d")
    by_n = {c["n"]: c for c in cards}
    out = {}
    for n, inf in fresh.items():
        pid = pids.get(n)
        if not pid or any(slot_value(inf, sl) for sl in slots if sl["t"] != "none"):
            continue
        if (inf.get("jtAt") or "") > soon:
            continue
        out[n] = (pid, (by_n.get(n) or {}).get("rarity", ""))
    return out


# ---------- chart history from JustTCG ----------
# Once per card, a year of JustTCG's daily prices for each condition fills in the chart for the days before the
# binder started saving that card's prices. It's kept apart from the binder's own prices, in jt_history.json:
# {"set": JustTCG's id for a set binder's set, "next": where a set fill stopped, "cards": {card: {"at": day asked,
# "c": {"NM": [[day, price], ...], ...}}}}, with only the days a price changed.
# A set binder asks for its whole set, 20 cards to a request; other binders ask about each card you own on its own.
jt_fill = {"running": False, "sid": "", "done": 0, "total": 0, "message": ""}


def jt_history_points(card, rarity=""):
    """{"NM": [[day, price], ...], ...} from one JustTCG card's price history, only the days the price changed."""
    out = {}
    for v in jt_variants(card, rarity):
        short = JT_COND.get(v.get("condition"))
        if not short or short in out:
            continue
        pts = []
        for h in sorted((h for h in v.get("priceHistory") or [] if isinstance(h, dict)), key=lambda h: h.get("t") or 0):
            if not (_is_num(h.get("t")) and _is_num(h.get("p")) and h["p"] > 0):
                continue
            d, p = time.strftime("%Y-%m-%d", time.gmtime(h["t"])), round(h["p"], 2)
            if pts and pts[-1][0] == d:
                pts[-1][1] = p
            elif not pts or pts[-1][1] != p:
                pts.append([d, p])
        if pts:
            out[short] = pts
    return out


def jt_history_doc(sid):
    doc = read_json(sdir(sid, "jt_history.json"), {})
    doc = doc if isinstance(doc, dict) else {}
    doc["cards"] = doc.get("cards") if isinstance(doc.get("cards"), dict) else {}
    return doc


def jt_keep_history(sid, got, **extra):
    """Add {card: points} (and extra fields like set or next) to the binder's JustTCG history, read fresh so
    two fills never undo each other."""
    with lock:
        doc = jt_history_doc(sid)
        for n, pts in got.items():
            doc["cards"][n] = {"at": today_local(), "c": pts}
        doc.update(extra)
        write_json(sdir(sid, "jt_history.json"), doc)


def jt_binder_cards(sid):
    """{card: (TCGplayer id, rarity, owned)} for the binder's cards that have a TCGplayer id."""
    ids = read_json(sdir(sid, "tcg_ids.json"), {})
    coll = read_json(sdir(sid, "collection.json"), {})
    out = {}
    for c in set_cards(sid):
        pid = tcg_product(c.get("tcg")) if c.get("custom") else ids.get(card_ref(sid, c)[0] or "")
        if pid:
            rec = coll.get(c["n"]) if isinstance(coll, dict) and isinstance(coll.get(c["n"]), dict) else {}
            out[c["n"]] = (str(pid), c.get("rarity", ""), (rec.get("qty") or 0) > 0)
    return out


def jt_history_query(**q):
    return "/cards?" + urllib.parse.urlencode(dict(q, include_price_history="true", priceHistoryDuration="1y"))


def jt_fill_card(sid, n):
    """Fill one card's chart history (1 request)."""
    card = jt_binder_cards(sid).get(n)
    if not card:
        raise JustTcgError("This card has no TCGplayer link yet, so JustTCG can't find it. Try after the next price check.", 400)
    if justtcg_left() <= 0:
        raise JustTcgError("The binder's JustTCG request limit is used up for now (Settings → Prices).", 429)
    ans = justtcg_call(jt_history_query(tcgplayerId=card[0]))
    found = (ans.get("data") or [None])[0]
    extra = {}
    if isinstance(found, dict) and found.get("set") and not is_multi(sid) and not jt_history_doc(sid).get("set"):
        extra["set"] = str(found["set"])[:120]
    jt_keep_history(sid, {n: jt_history_points(found, card[1])}, **extra)
    return {"ok": True, "found": bool(found)}


def jt_fill_plan(sid):
    """What filling the binder's chart history would take: {"cards": not filled yet, "requests": about how many}."""
    doc, cards = jt_history_doc(sid), jt_binder_cards(sid)
    if is_multi(sid):
        left = [n for n, (_, _, owned) in cards.items() if owned and n not in doc["cards"]]
        return {"cards": len(left), "requests": len(left)}
    left = [n for n in cards if n not in doc["cards"]]
    pages = -(-max(0, len(set_cards(sid)) - int(doc.get("next") or 0)) // JT_BATCH)
    return {"cards": len(left), "requests": (pages + (0 if doc.get("set") else 1)) if left else 0}


def jt_fill_status(sid):
    out = dict(jt_fill_plan(sid), job=dict(jt_fill), owned=is_multi(sid))   # owned: only the cards you own get filled
    if jt_fill["sid"] != sid:
        out["job"] = {"running": False, "message": ""}
    return out


def jt_fill_binder(sid):
    """Fill the chart history for a whole binder, within the request limits (runs in the background)."""
    asked, stop = 0, False
    try:
        cards = jt_binder_cards(sid)
        doc = jt_history_doc(sid)
        if is_multi(sid):   # cards from many sets: one request per card you own
            for n in [n for n, v in cards.items() if v[2] and n not in doc["cards"]]:
                if justtcg_left() <= 0:
                    stop = True
                    break
                if asked:
                    time.sleep(7)   # the free plan allows 10 requests a minute
                jt_fill_card(sid, n)
                asked += 1
                jt_fill["done"] = asked
        elif any(n not in doc["cards"] for n in cards):
            if not doc.get("set"):   # the first card also says which JustTCG set this is
                jt_fill_card(sid, next(n for n in cards if n not in doc["cards"]))
                asked += 1
                jt_fill["done"] = asked
                doc = jt_history_doc(sid)
            by_pid = {v[0]: (n, v[1]) for n, v in cards.items() if n not in doc["cards"]}
            offset = int(doc.get("next") or 0)
            while doc.get("set") and by_pid:
                if justtcg_left() <= 0:
                    stop = True
                    break
                if asked:
                    time.sleep(7)
                ans = justtcg_call(jt_history_query(game="pokemon", set=doc["set"], limit=JT_BATCH, offset=offset))
                asked += 1
                jt_fill["done"] = asked
                got = {}
                for c in ans.get("data") or []:
                    hit = by_pid.pop(str(c.get("tcgplayerId")), None) if isinstance(c, dict) else None
                    if hit:
                        got[hit[0]] = jt_history_points(c, hit[1])
                more = bool((ans.get("meta") or {}).get("hasMore")) and bool(ans.get("data"))
                offset = offset + JT_BATCH if more else 0
                jt_keep_history(sid, got, next=offset)
                if not more:
                    break
        left = jt_fill_plan(sid)["cards"]
        jt_fill["message"] = (f"Done: {asked} request{'s' if asked != 1 else ''}."
                              + (f" {left} cards wait until the request limit allows more." if stop and left else ""))
        log(f"{sid}: JustTCG chart history: {asked} requests, {left} cards not filled")
    except JustTcgError as e:
        jt_fill["message"] = str(e)
    except Exception as e:
        jt_fill["message"] = f"Filling chart history stopped: {hide_secrets(str(e))[:200]}"
        log(f"{sid}: JustTCG chart history failed: {hide_secrets(str(e))[:200]}")
    finally:
        jt_fill["running"] = False


def jt_start_fill(sid):
    """Start filling a binder's chart history in the background. False if a fill is already running."""
    with jt_lock:
        if jt_fill["running"]:
            return False
        jt_fill.update(running=True, sid=sid, done=0, total=jt_fill_plan(sid)["requests"], message="")
    threading.Thread(target=jt_fill_binder, args=(sid,), daemon=True).start()
    return True


def jt_chart(sid, n, points, cond, src, slots):
    """Put JustTCG's history in front of one card's chart lines, for the days before the binder's own prices.
    Returns (points, cond, src, about): about says whether the card is filled and where JustTCG's days end."""
    h = jt_history_doc(sid)["cards"].get(n)
    if not isinstance(h, dict):
        return points, cond, src, {"filled": False}
    jc = {c: [p for p in pts if isinstance(p, list) and len(p) == 2 and _is_num(p[1])]
          for c, pts in (h.get("c") if isinstance(h.get("c"), dict) else {}).items() if c in COND_ORDER and isinstance(pts, list)}
    until, today = {}, today_local()
    for c, pts in jc.items():
        own = cond.get(c) or []
        start = own[0][0] if own else today
        add = [p for p in pts if p[0] < start]
        if add:
            cond[c] = add + own
            until[c] = start
    raw = [sl["c"] for sl in slots if sl["t"] == "raw"]
    start = points[0][0] if points else today
    if raw and len(raw) == len([sl for sl in slots if sl["t"] != "none"]) and all(jc.get(c) for c in raw):
        # the binder's price average from JustTCG's conditions, each carried forward, one point a day like its own
        last, add, first = {}, [], min((jc[c][0][0] for c in raw), default="9999")
        day = datetime.strptime(first, "%Y-%m-%d") if first < start else None
        while day and len(add) < 800:
            d = day.strftime("%Y-%m-%d")
            if d >= start or d > today:
                break
            for c in raw:
                for p in jc[c]:
                    if p[0] <= d:
                        last[c] = p[1]
            if all(c in last for c in raw):
                add.append([d, round(sum(last[c] for c in raw) / len(raw), 2)])
            day += timedelta(days=1)
        if add:
            until["price"] = start
            lead = [[add[0][0], "justtcg"]]
            if points and (not src or src[0][0] > points[0][0]):   # own days from before sources were saved show "–"
                lead.append([points[0][0], ""])
            points, src = add + points, lead + src
    return points, cond, src, {"filled": True, "at": h.get("at", ""), "until": until}
