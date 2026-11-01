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


def jt_prices(card, rarity=""):
    """{"NM": [price, "YYYY-MM-DD"], ...} for the binder's kind of copy (English, not 1st Edition, holo or not
    like the card) from one JustTCG card, leaving out prices older than JT_STALE days."""
    holo = "holo" in (rarity or "").lower() and "reverse" not in (rarity or "").lower()
    variants = [v for v in (card or {}).get("variants") or [] if isinstance(v, dict)
                and "1st" not in str(v.get("printing")) and v.get("language") in (None, "", "English")]
    printings = {str(v.get("printing") or "") for v in variants}
    if len(printings) > 1:   # more than one kind: holo (not reverse) for a holo card, the plain one otherwise
        variants = [v for v in variants if ("holo" in str(v.get("printing")).lower()
                                            and "reverse" not in str(v.get("printing")).lower()) == holo]
    out, now = {}, time.time()
    for v in variants:
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
