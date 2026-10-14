"""Smoke test for Pokemon Binder: run it before every release.

    python3 tests/smoke_test.py

It copies server.py and index.html into a temporary folder, writes a small binder in the old JSON layout,
starts the binder on a spare port (nothing outside the temporary folder is touched, no downloads are needed),
and checks that the main pages answer, data moves into the database, saves stick, and backups restore.
Prints PASS or FAIL for each check and exits with 1 if anything failed. Python standard library only.
"""
import io, json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.error, urllib.request, zipfile

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
    write(root, "sets/neo4/cards.json", [{"n": str(i), "name": f"Card {i}", "num": str(i), "pt": "105", "rarity": "Rare"} for i in (1, 2, 3)])
    write(root, "sets/neo4/collection.json", {"1": {"qty": 1, "purchases": [{"d": "2026-10-01", "price": 20, "where": "eBay"}], "cond": "LP"}})
    write(root, "sets/neo4/prices.json", {"p": {"1": [25.0], "2": [10.0]}, "info": {"1": {"cond": {"LP": [25.0, 5, "2026-10-01"]},
                                          "recent": {"LP": [["2026-10-01", 25.0]]}, "src": "sales"}}, "updated": "2026-10-12T07:00:00Z"})
    write(root, "sets/neo4/history.json", {"2026-10-11": {"1": 24.0, "2": 9.0}, "2026-10-12": {"1": 25.0, "2": 10.0}})


def main():
    tmp = tempfile.mkdtemp(prefix="binder-smoke-")
    proc = None
    try:
        for name in ("server.py", "index.html"):
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

        rec = {"qty": 2, "purchases": [{"d": "2026-10-13", "price": 7.5, "where": "Card show"}, {"d": "", "price": None, "where": ""}], "cond": "MP"}
        code, _ = call(base, "PUT", "/api/set/neo4/card/2", rec)
        check("save a card", code == 200, f"got {code}")
        _, st = call(base, "GET", "/api/set/neo4/state")
        check("saved card reads back", st["collection"].get("2") == rec)
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
        check("restore brought the card back", st["collection"].get("2") == rec)

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
