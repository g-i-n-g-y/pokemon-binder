"""Smoke test for Pokemon Binder: run it before every release.

    python3 tests/smoke_test.py

It copies server.py, index.html and fonts.css into a temporary folder, writes a small binder in the old JSON layout,
starts the binder on a spare port (nothing outside the temporary folder is touched, no downloads are needed),
and checks that the main pages answer, data moves into the database, saves stick, and backups restore.
Prints PASS or FAIL for each check and exits with 1 if anything failed. Python standard library only.
"""
import io, json, os, re, shutil, socket, subprocess, sys, tempfile, time, urllib.error, urllib.request, zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
failed = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok or not detail else f"  ({detail})"))
    if not ok:
        failed.append(name)


def call(base, method, path, body=None, ctype="application/json"):
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": ctype, "Origin": base})
    try:
        with OPENER.open(req, timeout=30) as r:
            raw, code = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, code = e.read(), e.code
    try:
        return code, json.loads(raw)
    except ValueError:
        return code, raw


def write(root, rel, obj):
    path = os.path.join(root, "data", rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f)


def sample_binder(root):
    write(root, "sets.json", {"order": ["neo4"], "meta": {"neo4": {"id": "neo4", "name": "Neo Destiny", "series": "Neo",
                                                                    "printedTotal": 105, "total": 3, "releaseDate": "2002/02/28"}}})
    write(root, "settings.json", {"auto": False, "time": "03:00", "tz": "America/New_York"})
    write(root, "shows.json", {"shows": {}, "areas": ["Richmond"], "auto": False})
    write(root, "sets/neo4/cards.json", [{"n": str(i), "name": f"Card {i}", "num": str(i), "pt": "105", "rarity": "Rare", "type": "Pokémon"} for i in (1, 2, 3)])
    write(root, "sets/neo4/collection.json", {"1": {"qty": 1, "purchases": [{"d": "2026-10-01", "price": 20, "where": "eBay"}], "cond": "LP"}})
    write(root, "sets/neo4/prices.json", {"p": {"1": [25.0], "2": [10.0]}, "info": {"1": {"cond": {"LP": [25.0, 5, "2026-10-01"]},
                                          "recent": {"LP": [["2026-10-01", 25.0]]}, "src": "sales"}}, "updated": "2026-10-12T07:00:00Z"})
    write(root, "sets/neo4/history.json", {"2026-10-11": {"1": 24.0, "2": 9.0}, "2026-10-12": {"1": 25.0, "2": 10.0}})
    write(root, "catalog.json", {"fetched": time.time(), "sets": [{"id": "neo4", "name": "Neo Destiny", "series": "Neo",
                                  "printedTotal": 105, "total": 3, "releaseDate": "2002/02/28"}]})
    # a tiny every-card list for Find a card (the real one is made from the card database)
    with open(os.path.join(root, "data", "card_index.json"), "w") as f:
        json.dump({"fetched": time.time(),
                   "sets": {"neo1": ["Neo Genesis", "Neo", 111, "2000/12/16", 111], "neo4": ["Neo Destiny", "Neo", 105, "2002/02/28", 113],
                            "base1": ["Base", "Base", 102, "1999/01/09", 102]},
                   "cards": [["neo1-80", "Totodile", "80", "Common", "Pokémon", "", "neo1", 158],
                             ["neo1-81", "Totodile", "81", "Common", "Pokémon", "", "neo1", 158],
                             ["neo4-1", "Card 1", "1", "Rare", "Pokémon", "", "neo4", 0],
                             ["base1-4", "Charizard", "4", "Rare Holo", "Pokémon", "", "base1", 6],
                             ["base1-58", "Pikachu", "58", "Common", "Pokémon", "", "base1", 25]]}, f)


# Checks of small helpers, run inside the test folder (imports server.py without starting it).
UNIT = r"""
import server
cards = [{"n": str(i)} for i in range(1, 10)] + [{"n": "c1", "custom": True}]
server.write_json(server.sdir("unittest", "collection.json"), {"1": {"qty": 1}, "5": {"qty": 0}})
picks = [set(c["n"] for c in server.daily_cards("unittest", cards, day=d)) for d in (0, 1, 2)]
rest = set(str(i) for i in range(2, 10))
assert all({"1", "c1"} <= p for p in picks), picks
assert set().union(*picks) >= rest and all(len(p - {"1", "c1"}) <= 3 for p in picks), picks
assert server.AUTO_NAME_RE.fullmatch("daily-20261014-030000.zip")
assert server.backup_kind("daily") == "daily" and server.backup_kind("before-update") == "update"
assert server.small_url("https://images.pokemontcg.io/neo4/1_hires.png") == "https://images.pokemontcg.io/neo4/1.png"
import time
sl = server.sets_list(); sl["meta"]["neo4"]["added"] = int(time.time()); server.write_json(server.SETS_FILE, sl)
server.start_images("neo4")
assert "neo4" not in server.img_jobs, "a brand new binder started the big picture download"
# one big job at a time
with server.big_job("an update"):
    try:
        with server.big_job("a restore"):
            raise AssertionError("two big jobs ran at once")
    except server.Busy:
        pass
    assert server.refresh_prices("neo4", "test") is False, "a price check started during an update"
assert server.big["what"] == "", "the big-job slot wasn't freed"
with server.big_job("an update") as slot:
    slot["keep"] = True
assert server.big["what"] == "an update", "an update that restarts the binder should hold the slot"
server.big["what"] = ""
try:
    with server.big_job("a restore"):
        raise ValueError("bad file")
except ValueError:
    pass
assert server.big["what"] == "", "a failed job should free the slot"
server.job["running"] = True
try:
    with server.big_job("an update"):
        raise AssertionError("an update started during a price check")
except server.Busy as e:
    assert "price check" in str(e)
server.job["running"] = False
assert server.Handler.timeout and server.Handler.timeout <= 120
# background steps: an error in one is logged, not fatal
assert server.safely("test step", lambda: 1 / 0) is None
assert server.safely("test step", lambda: 5) == 5
# leftovers from a binder stopped partway are cleaned at start; fresh ones are left alone
import os
old_t = time.time() - 7200
for path in (".trial-abc/x.json", "tmp123.zip", "server.py.tmp", "data/sets/neo4/images/s/9.png.1.tmp", "backups/daily-1.zip.tmp"):
    full = os.path.join(server.APP, path); os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w").write("x"); os.utime(full, (old_t, old_t))
os.utime(os.path.join(server.APP, ".trial-abc"), (old_t, old_t))
open(os.path.join(server.APP, "fresh.tmp"), "w").write("x")
assert server.clean_leftovers() == 5
assert os.path.exists(os.path.join(server.APP, "fresh.tmp")) and os.path.exists(os.path.join(server.APP, "server.py"))
os.remove(os.path.join(server.APP, "fresh.tmp"))
# picture download misses aren't Status problems, real problems are
for m in ("image neo4-1: timed out", "Pokémon art 158: timed out", "neo3: set logo: HTTP Error 404"):
    assert server.PICTURE_MISS_RE.search(m), m
assert not server.PICTURE_MISS_RE.search("neo4: price refresh failed: timed out")
print("ok")
"""


def main():
    tmp = tempfile.mkdtemp(prefix="binder-smoke-")
    proc = None
    try:
        for name in ("server.py", "index.html", "fonts.css"):
            shutil.copyfile(os.path.join(REPO, name), os.path.join(tmp, name))
        sample_binder(tmp)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        log = open(os.path.join(tmp, "server.log"), "w+")
        # BINDER_TRIAL: answer pages only (no downloads, no schedule), like the update test start
        proc = subprocess.Popen([sys.executable, "-u", "server.py"], cwd=tmp, stdout=log, stderr=subprocess.STDOUT,
                                env=dict(os.environ, BINDER_PORT=str(port), BINDER_TRIAL="1", GITHUB_REPO=""))
        for _ in range(60):
            try:
                OPENER.open(base + "/", timeout=2)
                break
            except OSError:
                if proc.poll() is not None:
                    break
                time.sleep(0.25)
        check("binder starts", proc.poll() is None)
        if proc.poll() is not None:
            log.seek(0)
            print(log.read()[-2000:])
            return

        check("data moved into the database", os.path.isfile(os.path.join(tmp, "data", "binder.db"))
              and not os.path.exists(os.path.join(tmp, "data", "sets", "neo4", "collection.json")))
        for page in ("/", "/api/sets", "/api/settings", "/api/shows", "/api/spending", "/api/version", "/api/backups",
                     "/api/set/neo4/state", "/api/set/neo4/history", "/api/set/neo4/template.csv"):
            code, _ = call(base, "GET", page)
            check(f"GET {page}", code == 200, f"got {code}")

        code, st = call(base, "GET", "/api/set/neo4/state")
        check("collection came across", code == 200 and st["collection"]["1"]["purchases"][0]["price"] == 20)
        check("prices came across", code == 200 and st["prices"]["p"]["1"] == [25.0])
        code, hist = call(base, "GET", "/api/set/neo4/history")
        check("price history came across", hist == {"2026-10-11": {"1": 24.0, "2": 9.0}, "2026-10-12": {"1": 25.0, "2": 10.0}})
        code, tr = call(base, "GET", "/api/set/neo4/trends?today=2026-10-13")
        c1 = (tr.get("cards") or {}).get("1", {}) if isinstance(tr, dict) else {}
        check("price change summary", code == 200 and tr.get("first") == "2026-10-11" and c1.get("count") == 2
              and c1.get("at", {}).get("1") == ["2026-10-12", 25.0] and c1.get("first") == ["2026-10-11", 24.0], tr)
        code, one = call(base, "GET", "/api/set/neo4/history?card=2")
        check("one card's price chart", code == 200 and one.get("points") == [["2026-10-11", 9.0], ["2026-10-12", 10.0]], one)
        code, _ = call(base, "GET", "/api/set/neo4/history?card=../x")
        check("bad card name is turned down", code == 400)
        code, raw = call(base, "GET", "/")
        req = urllib.request.Request(base + "/", headers={"Accept-Encoding": "gzip"})
        with OPENER.open(req, timeout=10) as r:
            squeezed, enc, etag = r.read(), r.headers.get("Content-Encoding"), r.headers.get("ETag")
        check("page is sent compressed", enc == "gzip" and len(squeezed) < len(raw) / 2)
        try:
            OPENER.open(urllib.request.Request(base + "/", headers={"If-None-Match": etag}), timeout=10)
            check("unchanged page isn't sent again", False)
        except urllib.error.HTTPError as e:
            check("unchanged page isn't sent again", e.code == 304)

        req = urllib.request.Request(base + "/fonts.css")
        with OPENER.open(req, timeout=10) as r:
            css, ctype, cache = r.read(), r.headers.get("Content-Type", ""), r.headers.get("Cache-Control", "")
        check("fonts come from the binder itself", b"@font-face" in css and "text/css" in ctype and "immutable" in cache, (ctype, cache))
        check("page doesn't ask Google for fonts", b"fonts.googleapis" not in raw and b"fonts.css" in raw)
        code, h = call(base, "GET", "/api/health")
        check("health check answers", code == 200 and h.get("ok") is True, h)
        code, stt = call(base, "GET", "/api/status")
        check("status answers", code == 200 and all(k in stt for k in ("lastRefresh", "lastBackup", "dbSize", "pictures", "freeSpace", "problems"))
              and stt["dbSize"] > 0 and stt["lastRefresh"] > 0, stt)
        for q in ("", "?full=1"):
            code, _ = call(base, "GET", "/set/neo4/img/1.png" + q)
            check("missing card picture is a clean 404" + (" (full size)" if q else ""), code == 404, f"got {code}")
        code, _ = call(base, "PUT", "/api/settings", {"refreshAll": True})
        _, sett = call(base, "GET", "/api/settings")
        check("save 'check every card every night'", code == 200 and sett.get("refreshAll") is True, sett.get("refreshAll"))
        code, _ = call(base, "POST", "/api/sets/neo4/pictures", {})
        check("get pictures now starts", code == 200, f"got {code}")
        code, _ = call(base, "POST", "/api/sets/nope/pictures", {})
        check("get pictures for a missing binder is turned down", code == 404, f"got {code}")
        _, sl = call(base, "GET", "/api/sets")
        check("sets list says how many pictures are saved", "pics" in sl["sets"][0], sl["sets"][0].keys())
        unit = subprocess.run([sys.executable, "-c", UNIT], cwd=tmp, capture_output=True, text=True, timeout=60)
        check("nightly check picks owned cards plus a third of the rest", unit.stdout.strip().splitlines()[-1:] == ["ok"], (unit.stdout + unit.stderr)[-600:])

        rec = {"qty": 2, "purchases": [{"d": "2026-10-13", "price": 7.5, "where": "Card show"}, {"d": "", "price": None, "where": ""}], "cond": "MP"}
        code, _ = call(base, "PUT", "/api/set/neo4/card/2", rec)
        check("save a card", code == 200, f"got {code}")
        _, st = call(base, "GET", "/api/set/neo4/state")
        saved = dict(st["collection"].get("2") or {})
        got = saved.pop("got", None)
        check("saved card reads back", saved == rec)
        check("the day a card was first owned is remembered", bool(got and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d", got)), got)
        call(base, "PUT", "/api/set/neo4/card/2", dict(rec, qty=3))
        _, st = call(base, "GET", "/api/set/neo4/state")
        check("that day stays when the card is saved again", st["collection"].get("2", {}).get("got") == got, st["collection"].get("2"))
        call(base, "PUT", "/api/set/neo4/card/2", rec)
        code, home = call(base, "GET", "/api/home")
        nb = next((b for b in (home or {}).get("binders", []) if b["id"] == "neo4"), None) if code == 200 else None
        check("home page lists binders with completion and a cover", bool(nb and nb["count"] and "owned" in nb and nb.get("cover", {}).get("n")), nb)
        check("home page lists recently added cards", code == 200 and any(r["sid"] == "neo4" and r["n"] == "2" for r in home.get("recent", [])), (home or {}).get("recent"))
        req = urllib.request.Request(base + "/api/export.xlsx")
        with urllib.request.urlopen(req, timeout=20) as r:
            xz = zipfile.ZipFile(io.BytesIO(r.read()))
        sheet = xz.read("xl/worksheets/sheet1.xml").decode()
        check("spreadsheet export has every binder and the saved card", "xl/workbook.xml" in xz.namelist() and "Owned" in sheet and "Card 2" in sheet, xz.namelist())
        code, _ = call(base, "PUT", "/api/settings", {"time": "04:15"})
        _, sett = call(base, "GET", "/api/settings")
        check("save settings", code == 200 and sett.get("time") == "04:15")
        code, _ = call(base, "PUT", "/api/settings", {"serverName": "  My  NAS "})
        _, sett = call(base, "GET", "/api/settings")
        check("save a server name", code == 200 and sett.get("serverName") == "My NAS", sett.get("serverName"))
        code, _ = call(base, "PUT", "/api/settings", {"serverName": "<script>"})
        check("odd server names are turned down", code == 400)
        code, sp = call(base, "GET", "/api/spending")
        check("Stats adds up", code == 200 and sp["totals"]["spent"] == 27.5, sp.get("totals") if isinstance(sp, dict) else code)

        code, svg = call(base, "POST", "/api/set/neo4/photo/1", b"<svg/>", "image/svg+xml")
        check("SVG photos are turned down", code == 400)
        code, _ = call(base, "POST", "/api/set/neo4/photo/1", b"\x89PNG\r\n\x1a\nsmoke", "image/png")
        check("PNG photo uploads", code == 200)
        code, _ = call(base, "PUT", "/api/set/neo4/card/3", b"{not json")
        check("bad input gets an error, not a crash", code == 400)
        code, _ = call(base, "POST", "/api/refresh", b"{not json")
        check("bad refresh request gets an error", code == 400)
        req = urllib.request.Request(base + "/api/set/neo4/card/1", data=b"{}", method="PUT",
                                     headers={"Content-Type": "application/json", "Origin": "http://evil.example"})
        try:
            OPENER.open(req, timeout=10)
            check("changes from other websites are blocked", False)
        except urllib.error.HTTPError as e:
            check("changes from other websites are blocked", e.code == 403)

        code, zipped = call(base, "GET", "/api/backup")
        names = zipfile.ZipFile(io.BytesIO(zipped)).namelist() if code == 200 else []
        check("backup downloads", code == 200 and "sets/neo4/collection.json" in names and "sets/neo4/photos/1" in names, names[:5])
        call(base, "PUT", "/api/set/neo4/card/2", {"qty": 0, "purchases": []})
        code, res = call(base, "POST", "/api/restore", zipped, "application/zip")
        check("backup restores", code == 200, res)
        _, st = call(base, "GET", "/api/set/neo4/state")
        check("restore brought the card back", {k: v for k, v in (st["collection"].get("2") or {}).items() if k != "got"} == rec)

        # Find a card, your own binders and the Pages view (v3.8)
        q = urllib.parse.quote
        code, r = call(base, "GET", "/api/find?q=" + q("Totodile 80/111"))
        check("find a card by name and number", code == 200 and [c["n"] for c in r["cards"]] == ["neo1-80"], str(r)[:200])
        code, r = call(base, "GET", "/api/find?q=" + q("neo genesis"))
        check("find a set by name", code == 200 and r["sets"] and r["sets"][0]["id"] == "neo1")
        code, r = call(base, "GET", "/api/find?q=" + q("1/105"))
        check("search says which binders have a card", code == 200 and r["cards"] and r["cards"][0]["in"][0]["sid"] == "neo4", str(r)[:200])
        code, r = call(base, "GET", "/api/find/set/neo1")
        check("browse a whole set", code == 200 and len(r["cards"]) == 2)
        code, own = call(base, "POST", "/api/sets/own", {"name": "Favorites"})
        check("make your own binder", code == 200 and own.get("id") == "my-1", str(own))
        code, r = call(base, "POST", "/api/set/my-1/cards", {"id": "base1-4"})
        check("add a card to your own binder", code == 200 and r == {"n": "base1-4", "already": False}, str(r))
        code, r = call(base, "POST", "/api/set/neo4/cards", {"id": "neo4-1"})
        check("a set's own card isn't added twice", code == 200 and r.get("already") and r["n"] == "1", str(r))
        code, r = call(base, "POST", "/api/set/neo4/cards", {"id": "neo1-80"})
        check("add a card from another set to a set binder", code == 200 and r.get("already") is False, str(r))
        code, _ = call(base, "POST", "/api/set/my-1/cards", {"id": "nope-1"})
        check("unknown card is turned down", code == 400)
        _, st = call(base, "GET", "/api/set/my-1/state")
        check("your own binder lists its cards", [c["n"] for c in st["cards"]] == ["base1-4"] and st["cards"][0]["set"] == "Base")
        code, r = call(base, "PUT", "/api/set/neo4/layout", {"pockets": 9, "order": "num", "slots": ["2", None, "1", "bogus", "1"]})
        check("save a binder layout", code == 200 and r.get("slots") == ["2", None, "1"], str(r))
        code, _ = call(base, "PUT", "/api/set/neo4/layout", {"pockets": 7})
        check("odd pocket sizes are turned down", code == 400)
        code, _ = call(base, "PUT", "/api/sets/my-1/name", {"name": "Faves"})
        check("rename your own binder", code == 200)
        code, _ = call(base, "PUT", "/api/sets/neo4/name", {"name": "X"})
        check("set binders can't be renamed", code == 400)
        code, r = call(base, "GET", "/api/set/my-1/dexnums")
        check("Pokédex numbers for the Pages view", code == 200 and r["dex"].get("base1-4") == 6, str(r))
        code, z = call(base, "GET", "/api/backup")
        names = zipfile.ZipFile(io.BytesIO(z)).namelist() if code == 200 else []
        check("backups hold added cards and layouts", "sets/my-1/extra.json" in names and "sets/neo4/layout.json" in names, str(names)[:300])
        code, _ = call(base, "DELETE", "/api/set/neo4/cards/1")
        check("a set's own cards can't be taken out", code == 400)
        code, _ = call(base, "DELETE", "/api/set/neo4/cards/neo1-80")
        check("take an added card back out", code == 200)
        _, st = call(base, "GET", "/api/set/neo4/state")
        check("taken-out card is gone", not any(c["n"] == "neo1-80" for c in st["cards"]))

        # card show mode: needed cards, the working-on pick, a one-tap buy and a synced buy with its condition
        code, show = call(base, "GET", "/api/show")
        need_before = len(show.get("cards", []))
        check("card show lists the cards you still need", code == 200 and need_before > 0, show)
        n_buy = next(c["n"] for c in show["cards"] if c["sid"] == "neo4")
        code, res = call(base, "POST", f"/api/set/neo4/card/{n_buy}/buy", {"purchase": {"id": "showbuy0001", "d": "2026-10-18", "price": 4.5, "where": "Show"}, "cond": "LP"})
        code2, res2 = call(base, "POST", f"/api/set/neo4/card/{n_buy}/buy", {"purchase": {"id": "showbuy0001", "d": "2026-10-18", "price": 4.5, "where": "Show"}, "cond": "LP"})
        _, st = call(base, "GET", "/api/set/neo4/state")
        rec = st["collection"].get(n_buy, {})
        check("Got it adds one copy with its condition, never twice", code == 200 and res.get("added") and res2.get("added") is False
              and rec.get("qty") == 1 and rec.get("cond") == "LP", (res, res2, rec))
        _, show = call(base, "GET", "/api/show")
        check("a bought card leaves the card show list", len(show["cards"]) == need_before - 1)
        code, _ = call(base, "PUT", "/api/settings", {"showBinders": ["neo4", "nope"]})
        _, home = call(base, "GET", "/api/home")
        check("working-on binders are saved and shown on the home page", code == 200 and home.get("working") == ["neo4"], home.get("working"))
        sync_card = show["cards"][0]
        n_sync = sync_card["n"]
        code, res = call(base, "POST", "/api/sync", {"changes": [{"sid": sync_card["sid"], "n": n_sync, "purchase": {"id": "showsync0001", "d": "2026-10-18", "price": 2}, "cond": "MP"}]})
        _, st = call(base, "GET", f"/api/set/{sync_card['sid']}/state")
        check("an offline card show buy syncs with its condition", code == 200 and st["collection"].get(n_sync, {}).get("cond") == "MP", st["collection"].get(n_sync))

        # removing a binder and adding it again asks whether to bring its cards back or start fresh
        owned = lambda: next((b["owned"] for b in call(base, "GET", "/api/home")[1]["binders"] if b["id"] == "neo4"), None)
        before = owned()
        call(base, "DELETE", "/api/sets/neo4")
        code, res = call(base, "POST", "/api/sets", {"id": "neo4"})
        check("adding a removed binder asks about its saved cards", code == 409 and res.get("saved", {}).get("owned") == before, res)
        code, res = call(base, "POST", "/api/sets", {"id": "neo4", "keep": True})
        check("restore brings the cards back", code == 200 and res.get("restored") and owned() == before, res)
        call(base, "DELETE", "/api/sets/neo4")
        code, res = call(base, "POST", "/api/sets", {"id": "neo4", "keep": False})
        check("start fresh adds it empty, with a backup first", code == 200 and owned() == 0
              and any(f.startswith("before-fresh-") for f in os.listdir(os.path.join(tmp, "backups"))), res)
        code, _ = call(base, "POST", "/api/sets", {"id": "neo4"})
        _, home = call(base, "GET", "/api/home")
        check("adding a binder that's already there doesn't ask", code == 200 and [b["id"] for b in home["binders"]].count("neo4") == 1)
        req = urllib.request.Request(base + "/api/set/my-1/cards", data=b'{"id":"base1-58"}', method="POST",
                                     headers={"Content-Type": "application/json", "Origin": "http://evil.example", "Sec-Fetch-Site": "cross-site"})
        try:
            OPENER.open(req, timeout=10); blocked = False
        except urllib.error.HTTPError as e:
            blocked = e.code == 403
        check("other websites can't add cards", blocked)

        page = open(os.path.join(REPO, "index.html"), encoding="utf-8").read()
        names = re.findall(r"^\s*(?:async\s+)?function\s+(\w+)\s*\(", page, re.M)
        twice = sorted({n for n in names if names.count(n) > 1})
        check("no two page functions share a name (the later one would replace the first)", not twice, twice)
        ids = re.findall(r'\sid="([^"]+)"', page.split("<script>")[0])
        twice_ids = sorted({i for i in ids if ids.count(i) > 1})
        check("no two page elements share an id (the code would only find the first)", not twice_ids, twice_ids)
        css = page.split("</style>")[0]
        priv = [r for r in re.findall(r"([^{}]+)\{([^}]*)\}", css) if "#sValue" in r[0] and "data-private" in r[0]]
        check("privacy mode blurs the money totals", bool(priv) and all("blur" in r[1] for r in priv), priv)
        srv = open(os.path.join(REPO, "server.py"), encoding="utf-8").read()
        defs = re.findall(r"^def (\w+)\(", srv, re.M)
        twice_defs = sorted({d for d in defs if defs.count(d) > 1})
        check("no two server functions share a name", not twice_defs, twice_defs)

        log.seek(0)
        text = log.read()
        check("no unexpected errors in the log", "Traceback" not in text, text[-800:])
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait(10)
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("All checks passed." if not failed else f"{len(failed)} check(s) failed: " + ", ".join(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
