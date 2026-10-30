"""Pokemon Binder - tiny self-hosted collection tracker you run on your own server.

- Any number of English sets, each in data/sets/<set id>/
- Card lists come from the PokemonTCG/pokemon-tcg-data project on GitHub
- Card images are downloaded to the server when a set is added
- Prices refresh once a day from TCGplayer recent sales (Unlimited, English, LP/MP)
- TCGdex (free, no key) adds TCGplayer market and Cardmarket prices as a backup and second opinion
Python standard library only. Listens on port 8080 inside the container.

Test one card's price lookup:  docker exec neo-binder python server.py --test neo4-107

Updates: only when you choose them. Settings -> About -> Check for updates shows what's new
from the public GitHub repository (GITHUB_REPO, default g-i-n-g-y/pokemon-binder) and asks
before installing anything. Restarting never installs updates. No key is needed. Set
GITHUB_REPO to an empty value to use a folder mounted at /updates instead (same button). GITHUB_TOKEN is optional and only
needed for a private copy of the repository. Replaced files are kept in previous/.
"""
from html import unescape
import ast, contextlib, gzip, io, json, os, unicodedata, re, shutil, socket, sqlite3, subprocess, sys, tempfile, threading, time, traceback, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
try:
    from zoneinfo import ZoneInfo
except ImportError:  # very old Python
    ZoneInfo = None

APP_VERSION = "4.0"   # 3.0 big changes, 2.12 features, 2.11.1 small fixes (see CHANGELOG.md)

APP = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(APP, "data")
SETS_DIR = os.path.join(DATA, "sets")
SETS_FILE = os.path.join(DATA, "sets.json")
SETTINGS = os.path.join(DATA, "settings.json")
DEFAULT_SLOTS = [{"t": "raw", "c": "LP"}, {"t": "raw", "c": "MP"}]
DEFAULT_SETTINGS = {"auto": True, "time": "03:00", "tz": "America/New_York", "offset": -240, "lastAuto": "",
                    "slots": DEFAULT_SLOTS, "backup": True, "serverName": "", "refreshAll": False}
RAW_CONDS = ("NM", "LP", "MP", "HP", "DMG")
GRADERS = ("PSA", "BGS", "CGC", "SGC", "TAG", "ACE", "Any")
GRADES = ("10", "9.5", "9", "8.5", "8", "7.5", "7", "6", "5", "4", "3", "2", "1")
CATALOG = os.path.join(DATA, "catalog.json")
GH = "https://raw.githubusercontent.com/PokemonTCG/pokemon-tcg-data/master"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
WANT_COND = ("Lightly Played", "Moderately Played")   # updated from the price slots at each refresh
SALES_TO_AVERAGE = 10
DAY = 24 * 3600
MAX_PHOTO = 15 * 1024 * 1024
# Card photo types. SVG is left out on purpose: an SVG file can carry a script.
PHOTO_TYPES = ("image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif", "image/avif")
# BINDER_PORT and BINDER_TRIAL are only used by the update check, which test-starts a new version on a spare port.
PORT = int(os.environ.get("BINDER_PORT") or 8080)
TRIAL = os.environ.get("BINDER_TRIAL") == "1"
# Browser tab icon. Your own icon (uploaded in Settings) lives in data/, so it never goes into the repository.
ICON_FILE = os.path.join(DATA, "favicon")
ICON_TYPES = ("image/png", "image/jpeg", "image/webp", "image/gif", "image/x-icon", "image/vnd.microsoft.icon")
MAX_ICON = 2 * 1024 * 1024
DEFAULT_ICON = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect x="6" y="4" width="52" height="56" rx="8" fill="#2A2438"/>
<rect x="13" y="11" width="17" height="22" rx="3" fill="#A88BEA"/><rect x="34" y="11" width="17" height="22" rx="3" fill="#E2B04A"/>
<rect x="13" y="37" width="17" height="17" rx="3" fill="#5CC3CC"/><rect x="34" y="37" width="17" height="17" rx="3" fill="#6B6380"/>
</svg>"""
SID_RE = r"[a-z0-9][a-z0-9.\-]{0,40}"
NUM_RE = r"[A-Za-z0-9\-]{1,24}"
DEX_RE = re.compile(r"dex-(\d{1,4})")   # a Pokémon master set binder, like dex-158 for Totodile
DEX_INDEX = os.path.join(DATA, "dex_index.json")
CARD_INDEX = os.path.join(DATA, "card_index.json")   # every English card, for Find a card (made with the Pokémon list)
CARD_INDEX_V = 1   # bump when the every-card list gets new fields, so it's made again
OWN_RE = re.compile(r"my-(\d{1,5})")   # a binder you fill yourself, like my-1
SPRITES = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"

# The program files of THIS version. The updater reads this line from a new server.py to know what to download,
# so a later version can be split into more files. Versions before v3.0 only ever had these two.
# Keep it one plain list with no brackets inside: older versions read it with a simple pattern.
APP_FILES = ("server.py", "index.html", "fonts.css", "sw.js", "icon-192.png", "icon-512.png",
             "app/style.css", "app/core.js", "app/grid.js", "app/card.js", "app/copy.js", "app/settings.js",
             "app/updates.js", "app/sets.js", "app/data.js", "app/shop.js", "app/stats.js", "app/find.js",
             "app/pages.js", "app/show.js", "app/psa.js", "app/offline.js", "app/start.js",
             "binder/core.py", "binder/cards.py", "binder/psa.py", "binder/images.py", "binder/prices.py", "binder/history.py",
             "binder/shows.py", "binder/spreadsheet.py", "binder/backup.py", "binder/sync.py", "binder/web.py", "binder/pricetest.py",
             "binder/updater.py")
UPDATE_FILES = APP_FILES

# The rest of the server is in binder/, one file per part. They run here, in this order, exactly as if they were
# written in this file: they share its names, so a part can use anything from the parts before it.
SERVER_PARTS = ("core", "cards", "psa", "images", "prices", "history", "shows", "spreadsheet", "backup", "sync", "web", "pricetest", "updater")
for _part in SERVER_PARTS:
    _path = os.path.join(APP, "binder", _part + ".py")
    with open(_path, encoding="utf-8") as _f:
        exec(compile(_f.read(), _path, "exec"))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--test":
        test_card(sys.argv[2] if "-" in sys.argv[2] else f"neo4-{sys.argv[2]}")
        sys.exit(0)
    setup()
    load_other_hosts()
    if TRIAL:   # an update test start: answer pages only (no downloads, no schedule), and only on this machine
        def _no_downloads(*args, **kwargs):
            raise urllib.error.URLError("no downloads during an update test")
        urllib.request.urlopen = _no_downloads
        log(f"Pokemon Binder test start on port {PORT}")
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    safely("cleaning up leftover files", clean_leftovers)
    threading.Thread(target=warm_up, daemon=True).start()
    threading.Thread(target=scheduler, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()
    log(f"Pokemon Binder running on port {PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
