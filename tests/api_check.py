"""API check for Pokemon Binder: proves the server's answers didn't change while the code was rearranged.

    python3 tests/api_check.py          compare with tests/api_answers.json
    python3 tests/api_check.py --save   save the current answers as the new expected ones

It starts a small made-up binder (the same one the smoke test uses) in a temporary folder with every program file
(APP_FILES), then sends a fixed list of requests: reads of every page of the API, plus saves, in a fixed order.
Each answer's status code and body are compared with the saved ones. Values that change on every run (times, sizes,
today's date) are blanked out first. Nothing outside the temporary folder is touched, no downloads are needed.
Only save new answers when a change to the API is on purpose.
"""
import datetime, io, json, os, re, shutil, socket, subprocess, sys, tempfile, time, urllib.parse, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smoke_test import OPENER, REPO, call, copy_app, sample_binder   # noqa: E402

ANSWERS = os.path.join(REPO, "tests", "api_answers.json")
VERSION = re.search(r'^APP_VERSION = "([^"]+)"', open(os.path.join(REPO, "server.py"), encoding="utf-8").read(), re.M).group(1)
q = urllib.parse.quote

# The requests, in order. Saves come after the reads they change, so both before and after are checked.
STEPS = [
    ("GET", "/api/health"), ("GET", "/api/version"), ("GET", "/api/sets"), ("GET", "/api/settings"),
    ("GET", "/api/home"), ("GET", "/api/shows"), ("GET", "/api/spending"), ("GET", "/api/backups"),
    ("GET", "/api/progress"), ("GET", "/api/sellers"), ("GET", "/api/habit"), ("GET", "/api/show"),
    ("GET", "/api/changelog"), ("GET", "/api/icon"),
    ("GET", "/api/set/neo4/state"), ("GET", "/api/set/neo4/history"), ("GET", "/api/set/neo4/history?card=1"),
    ("GET", "/api/set/neo4/trends?today=2026-10-13"), ("GET", "/api/set/neo4/dexnums"),
    ("GET", "/api/set/neo4/template.csv"), ("GET", "/api/export.xlsx"),
    ("GET", "/api/find?q=" + q("Totodile 80/111")), ("GET", "/api/find?q=" + q("neo genesis")),
    ("GET", "/api/find?q=" + q("1/105")), ("GET", "/api/find/set/neo1"),
    ("GET", "/manifest.webmanifest"), ("GET", "/set/neo4/img/1.png"), ("GET", "/api/set/nope/state"),
    ("GET", "/api/set/neo4/history?card=../x"),
    # saves
    ("PUT", "/api/set/neo4/card/2", {"qty": 2, "cond": "MP", "purchases": [{"d": "2026-10-13", "price": 7.5, "where": "Card show"},
                                                                        {"d": "", "price": None, "where": "", "had": True, "rev": True}]}),
    ("PUT", "/api/set/neo4/card/3", "{not json"),
    ("PUT", "/api/settings", {"time": "04:15", "refreshAll": True}),
    ("PUT", "/api/settings", {"serverName": "<script>"}),
    ("POST", "/api/set/neo4/card/3/buy", {"purchase": {"id": "apicheck0001", "d": "2026-10-18", "price": 4.5, "where": "Show",
                                                       "seller": {"p": "instagram", "h": "CardGuy"}}, "cond": "LP"}),
    ("POST", "/api/set/neo4/card/3/buy", {"purchase": {"id": "apicheck0001", "d": "2026-10-18", "price": 4.5, "where": "Show"}}),
    ("POST", "/api/sync", {"changes": [{"sid": "neo4", "n": "1", "purchase": {"id": "apisync0001", "d": "2026-10-19", "price": 2}, "cond": "MP"}]}),
    ("POST", "/api/sets/own", {"name": "Favorites"}),
    ("POST", "/api/set/my-1/cards", {"id": "base1-4"}), ("POST", "/api/set/my-1/cards", {"id": "nope-1"}),
    ("POST", "/api/set/neo4/cards", {"id": "neo1-80"}),
    ("PUT", "/api/set/neo4/layout", {"pockets": 9, "order": "num", "slots": ["2", None, "1", "bogus", "1"]}),
    ("PUT", "/api/set/neo4/layout", {"pockets": 7}),
    ("PUT", "/api/sets/my-1/name", {"name": "Faves"}), ("PUT", "/api/sets/neo4/name", {"name": "X"}),
    ("POST", "/api/set/neo4/custom", {"name": "Promo Pikachu", "num": "P1", "rarity": "Promo"}),
    ("PUT", "/api/set/neo4/shop", {"mode": "mine", "order": ["3", "2", "3"], "upg": {"from": ["MP"], "to": "NM"}}),
    # reads again, after the saves
    ("GET", "/api/set/neo4/state"), ("GET", "/api/set/my-1/state"), ("GET", "/api/set/my-1/dexnums"),
    ("GET", "/api/home"), ("GET", "/api/sets"), ("GET", "/api/settings"), ("GET", "/api/spending"),
    ("GET", "/api/sellers"), ("GET", "/api/habit"), ("GET", "/api/show"), ("GET", "/api/progress"),
    ("DELETE", "/api/set/neo4/cards/neo1-80"), ("DELETE", "/api/set/neo4/cards/1"),
    ("GET", "/api/set/neo4/state"),
]

# Keys whose values change every run (times, sizes, counters that depend on the clock or the disk)
VOLATILE_KEYS = {"uptime", "dbSize", "freeSpace", "backupSize", "pictures", "lastRefresh", "lastBackup", "got", "mtime",
                 "size", "created", "checked", "installed", "fetched", "started", "ts", "etag"}
TIME_RE = re.compile(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d(:\d\d(\.\d+)?)?(Z|[+-]\d\d:?\d\d)?")


def scrub(v, key=""):
    """Blank out what changes from run to run, keep everything else exactly."""
    today = datetime.date.today().isoformat()
    if key in VOLATILE_KEYS and not isinstance(v, bool):
        return "<varies>"
    if isinstance(v, dict):
        return {k: scrub(x, k) for k, x in sorted(v.items())}
    if isinstance(v, list):
        return [scrub(x) for x in v]
    if isinstance(v, str):
        v = TIME_RE.sub("<time>", v)
        v = v.replace(today, "<today>")
        v = re.sub(r"\d{8}-\d{6}(-\d+)?", "<stamp>", v)   # backup file names
        return "<version>" if v == VERSION else v
    if isinstance(v, (int, float)) and not isinstance(v, bool) and 1.5e9 < v < 4e12:
        return "<time>"
    return v


def answer(base, method, path, body):
    data = body.encode() if isinstance(body, str) else body
    code, res = call(base, method, path, data if isinstance(data, bytes) else body)
    if isinstance(res, bytes):   # files: just what kind and whether they open
        kind = "zip" if res[:2] == b"PK" else "png" if res[:4] == b"\x89PNG" else "text" if res[:1].isascii() else "other"
        if kind == "zip":
            res = {"zip": sorted(zipfile.ZipFile(io.BytesIO(res)).namelist())}
        elif kind == "text" or res.startswith(b"\xef\xbb\xbf"):   # text, or text starting with a UTF-8 marker
            res = {"text": res.decode("utf-8", "replace")}
        else:
            res = {"file": kind}
    return {"status": code, "body": scrub(res)}


def run():
    tmp = tempfile.mkdtemp(prefix="binder-api-")
    proc = None
    try:
        copy_app(tmp)
        sample_binder(tmp)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        log = open(os.path.join(tmp, "server.log"), "w+")
        proc = subprocess.Popen([sys.executable, "-u", "server.py"], cwd=tmp, stdout=log, stderr=subprocess.STDOUT,
                                env=dict(os.environ, BINDER_PORT=str(port), BINDER_TRIAL="1", GITHUB_REPO=""))
        for _ in range(60):
            try:
                OPENER.open(base + "/", timeout=2)
                break
            except OSError:
                if proc.poll() is not None:
                    log.seek(0)
                    sys.exit("The binder didn't start:\n" + log.read()[-2000:])
                time.sleep(0.25)
        out = []
        for step in STEPS:
            method, path, body = (step + (None,))[:3]
            out.append({"request": f"{method} {path}", **answer(base, method, path, body)})
        return out
    finally:
        if proc:
            proc.terminate()
            proc.wait(10)
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    got = run()
    if "--save" in sys.argv:
        with open(ANSWERS, "w", encoding="utf-8", newline="\n") as f:
            json.dump(got, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"Saved {len(got)} answers to tests/api_answers.json")
        return
    try:
        want = json.load(open(ANSWERS, encoding="utf-8"))
    except OSError:
        sys.exit("No saved answers yet: run  python3 tests/api_check.py --save  on a version you trust")
    bad = 0
    for i, g in enumerate(got):
        w = want[i] if i < len(want) else None
        if g == w:
            continue
        bad += 1
        print(f"CHANGED  {g['request']}")
        print("   was: " + json.dumps(w and {k: w[k] for k in ("status", "body")}, ensure_ascii=False)[:600])
        print("   now: " + json.dumps({k: g[k] for k in ("status", "body")}, ensure_ascii=False)[:600])
    if len(want) != len(got):
        bad += 1
        print(f"CHANGED  number of requests: was {len(want)}, now {len(got)}")
    print(f"\n{len(got) - bad} of {len(got)} answers are the same." if bad else f"All {len(got)} answers are the same.")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
