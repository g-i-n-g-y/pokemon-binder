"""Web: which addresses are allowed, and every page and API address (Handler).

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

# ---------- web ----------

# Which web addresses the binder answers to. IP addresses, localhost, one-word names (like "myserver") and
# home/Tailscale names always work. Add others, like a reverse proxy name, in BINDER_HOSTS (comma separated).
# This blocks "DNS rebinding", where an outside website points its own name at your binder.
EXTRA_HOSTS = {h.strip().lower() for h in os.environ.get("BINDER_HOSTS", "").split(",") if h.strip()}
LOCAL_SUFFIXES = (".local", ".lan", ".home", ".home.arpa", ".internal", ".ts.net")


OTHER_HOSTS = set()   # extra addresses from Settings > Server > Other addresses (kept in step with settings.json)


def load_other_hosts():
    global OTHER_HOSTS
    try:
        OTHER_HOSTS = {h.lower() for h in (get_settings().get("otherHosts") or []) if isinstance(h, str)}
    except Exception:
        OTHER_HOSTS = set()


def clean_hosts(raw):
    """Settings > Server > Other addresses: names like binder.example.com or 203.0.113.5:8765, one per item."""
    items = raw if isinstance(raw, list) else re.split(r"[\s,]+", str(raw or ""))
    out = []
    for h in items:
        h = str(h).strip().lower()
        h = re.sub(r"^[a-z]+://", "", h).split("/")[0]   # people paste whole web addresses
        if not h:
            continue
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?)*(?::\d{1,5})?", h):
            raise ValueError(f"\"{h}\" doesn't look like a web address. Use a name like binder.example.com")
        if h not in out:
            out.append(h)
    if len(out) > 10:
        raise ValueError("Up to 10 other addresses")
    return out


def host_ok(host_header):
    h = (host_header or "").strip().lower()
    if h in OTHER_HOSTS:
        return True
    if h.startswith("["):                       # IPv6 like [::1]:8765
        return True
    name = h.rsplit(":", 1)[0] if h.count(":") == 1 else h
    if not name or name in EXTRA_HOSTS or name in OTHER_HOSTS or name == "localhost" or "." not in name:
        return True
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", name):
        return True
    return name.endswith(LOCAL_SUFFIXES)

# Text replies are squeezed with gzip before sending (every browser unpacks it): the page and binder data
# get about 4 times smaller, which matters most on a phone over Tailscale. Pictures are already compressed.
COMPRESSIBLE = {"application/json", "text/html", "text/plain", "text/csv", "image/svg+xml", "application/javascript", "text/css"}
_gz_cache = {}


def gzipped(body, etag=None):
    """gzip `body`; files with an ETag (the page, the fonts) are squeezed once and remembered."""
    if etag and etag in _gz_cache:
        return _gz_cache[etag]
    out = gzip.compress(body, 6)
    if etag:
        if len(_gz_cache) >= 8:
            _gz_cache.clear()
        _gz_cache[etag] = out
    return out


class Handler(BaseHTTPRequestHandler):
    # A device that connects and then goes quiet (a phone losing signal mid-load) is let go after a minute,
    # so it can't tie up part of the server for good. Only silence counts: slow uploads keep going.
    timeout = 60

    def log_message(self, fmt, *args):
        pass

    def send_response(self, code, message=None):
        self.replied = True
        super().send_response(code, message)

    def end_headers(self):
        # browsers must use the type we say (never guess a file is a web page)
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def send(self, code, body=b"", ctype="application/json", cache=None, etag=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        if etag and code == 200 and self.headers.get("If-None-Match") == etag:
            self.send_response(304)   # the browser already has this exact file
            self.send_header("ETag", etag)
            if cache:
                self.send_header("Cache-Control", cache)
            self.end_headers()
            return
        squeeze = ctype.split(";")[0].strip() in COMPRESSIBLE and len(body) > 1024
        if squeeze and "gzip" in (self.headers.get("Accept-Encoding") or "").lower():
            body = gzipped(body, etag)
        else:
            squeeze = False
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if squeeze:
            self.send_header("Content-Encoding", "gzip")
        if ctype.split(";")[0].strip() in COMPRESSIBLE:
            self.send_header("Vary", "Accept-Encoding")
        if cache:
            self.send_header("Cache-Control", cache)
        if etag:
            self.send_header("ETag", etag)
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, ctype, cache="max-age=604800"):
        try:
            st = os.stat(path)
            etag = f'"{st.st_mtime_ns:x}-{st.st_size:x}"'
            if self.headers.get("If-None-Match") == etag:
                return self.send(200, b"", ctype, cache, etag)
            with open(path, "rb") as f:
                self.send(200, f.read(), ctype, cache, etag)
        except OSError:
            self.send(404, b"not found", "text/plain")

    def body(self, limit):
        size = int(self.headers.get("Content-Length") or 0)
        if size <= 0 or size > limit:
            return None
        return self.rfile.read(size)

    def blocked(self, change):
        """Refuse requests sent to an unfamiliar address, and changes sent by another website.
        Browsers say where a request came from (Origin / Sec-Fetch-Site); changes must come from the binder's own page."""
        if not host_ok(self.headers.get("Host")):
            self.send(403, {"error": "Open the binder by its IP address (or add this name to BINDER_HOSTS)."})
            return True
        if change:
            site = (self.headers.get("Sec-Fetch-Site") or "").lower()
            origin = self.headers.get("Origin")
            if site and site not in ("same-origin", "none"):
                log(f"Blocked a {self.command} to {self.path} from another website ({site}).")
                self.send(403, {"error": "Changes can only come from the binder's own page."})
                return True
            if origin and origin != "null" and urllib.parse.urlparse(origin).netloc.lower() != (self.headers.get("Host") or "").lower():
                log(f"Blocked a {self.command} to {self.path} from {origin}.")
                self.send(403, {"error": "Changes can only come from the binder's own page."})
                return True
            if origin == "null":
                self.send(403, {"error": "Changes can only come from the binder's own page."})
                return True
        return False

    def in_binder(self, sid):
        return sid in sets_list()["order"]

    def do_GET(self):
        if self.blocked(False):
            return
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self.send_file(os.path.join(APP, "index.html"), "text/html; charset=utf-8", "no-cache")
        if path == "/manifest.webmanifest":   # lets Chrome install the binder as an app
            custom = os.path.exists(ICON_FILE) and read_json(ICON_FILE + ".json", {}).get("type") == "image/png"
            icons = ([{"src": "app-icon.png?v=" + str(int(os.path.getmtime(ICON_FILE))), "sizes": "512x512", "type": "image/png", "purpose": "any"}]
                     if custom else
                     [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                      {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}])
            man = {"name": "Pokémon Binder", "short_name": "Binder", "id": "./", "start_url": "./", "scope": "./",
                   "display": "standalone", "background_color": "#111213", "theme_color": "#111213", "icons": icons}
            return self.send(200, json.dumps(man).encode(), "application/manifest+json", "no-cache")
        if path == "/sw.js":   # the version goes in, so each binder update refreshes the phone's saved copies
            try:
                with open(os.path.join(APP, "sw.js"), "rb") as f:
                    body = f.read().replace(b"__VERSION__", APP_VERSION.encode()).replace(
                        b'"__APP_FILES__"', json.dumps([n for n in APP_FILES if n.startswith("app/")]).encode())
            except OSError:
                return self.send(404, b"not found", "text/plain")
            return self.send(200, body, "application/javascript; charset=utf-8", "no-cache")
        if path in ("/icon-192.png", "/icon-512.png"):
            return self.send_file(os.path.join(APP, path[1:]), "image/png")
        if path == "/app-icon.png":   # your own tab icon from Settings, used as the app icon too
            return self.send_file(ICON_FILE, "image/png", "no-cache")
        if path.startswith("/app/") and path[1:] in APP_FILES:   # the page's styles and code
            kind = "text/css; charset=utf-8" if path.endswith(".css") else "application/javascript; charset=utf-8"
            return self.send_file(os.path.join(APP, *path[1:].split("/")), kind, "no-cache")
        if path == "/fonts.css":   # fonts kept on the server; the page asks for fonts.css?v=<n>, so a new version means a new address
            return self.send_file(os.path.join(APP, "fonts.css"), "text/css; charset=utf-8", "max-age=31536000, immutable")
        m = re.fullmatch(r"/art/(\d{1,4})(s?)\.png", path)
        if m:
            try:
                return self.send_file(pokemon_art(m.group(1), m.group(2) == "s"), "image/png")
            except Exception as e:
                log(f"Pokémon art {m.group(1)}{m.group(2)}: {e}")
                return self.send(404, b"not found", "text/plain")
        m = re.fullmatch(r"/unown/([a-z])\.png", path)
        if m:
            try:
                return self.send_file(unown_sprite(m.group(1)), "image/png")
            except Exception as e:
                log(f"Unown {m.group(1)}: {e}")
                return self.send(404, b"not found", "text/plain")
        if path in ("/favicon", "/favicon.ico"):
            if os.path.exists(ICON_FILE):
                kind = read_json(ICON_FILE + ".json", {}).get("type")   # only a picture type, even from an edited backup
                return self.send_file(ICON_FILE, kind if kind in ICON_TYPES else "image/png", "no-cache")
            return self.send(200, DEFAULT_ICON, "image/svg+xml", "no-cache")
        if path == "/api/icon":
            return self.send(200, {"custom": os.path.exists(ICON_FILE)}, cache="no-store")
        if path == "/api/backups":
            return self.send(200, {"backups": list_auto_backups()}, cache="no-store")
        if path == "/api/export/tcgplayer.txt":   # for TCGplayer's Collection > Import; every binder, or just ?b=neo4,neo1
            want = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("b") or [""])[0]
            order = sets_list()["order"]
            only = [x for x in want.split(",") if x in order] if want else None
            if want and not only:
                return self.send(400, {"error": "None of those binders exist."})
            try:
                text, missed = export_tcgplayer(only)
            except Exception as e:
                log(f"TCGplayer download: {e}")
                return self.send(502, {"error": "Couldn't reach TCGplayer's card list. Try again in a few minutes."})
            body = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="tcgplayer-import-{time.strftime("%Y-%m-%d")}.txt"')
            self.send_header("X-Binder-Missed", str(len(missed)))   # owned cards TCGplayer's list didn't have
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/export.xlsx":   # every binder in one spreadsheet, or just ?b=neo4,neo1
            want = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("b") or [""])[0]
            order = sets_list()["order"]
            only = [x for x in want.split(",") if x in order] if want else None
            if want and not only:
                return self.send(400, {"error": "None of those binders exist."})
            body = export_collection(only)
            name = "pokemon-binder"
            if only and len(only) == 1:
                name += "-" + (re.sub(r"[^a-z0-9]+", "-", sets_list()["meta"].get(only[0], {}).get("name", only[0]).lower()).strip("-") or only[0])
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="{name}-{time.strftime("%Y-%m-%d")}.xlsx"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        m_tp = re.fullmatch(rf"/api/set/({SID_RE})/template\.csv", path)
        if m_tp:
            sid = m_tp.group(1)
            if not self.in_binder(sid) or is_dex(sid):
                return self.send(400, {"error": "Templates are for set binders"})
            body = import_template(sid)
            fname = re.sub(r"[^A-Za-z0-9]+", "-", sets_list()["meta"].get(sid, {}).get("name", sid)).strip("-") or sid
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="{fname}-binder-template.csv"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        m_bk = re.fullmatch(r"/api/backups/([A-Za-z0-9.\-]+)", path)
        if m_bk:
            name = m_bk.group(1)
            fp = os.path.join(BACKUPS, name)
            if not AUTO_NAME_RE.fullmatch(name) or not os.path.isfile(fp):
                return self.send(404, {"error": f"That backup isn't on {srv_name()} any more"})
            with open(fp, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="pokemon-binder-{name}"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/backup":
            buf = io.BytesIO()
            try:
                make_backup(buf)
            except Exception as e:
                return self.send(500, {"error": f"Couldn't make the backup: {e}"})
            body = buf.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="pokemon-binder-backup-{time.strftime("%Y-%m-%d")}.zip"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/version":
            return self.send(200, version_info(), cache="no-store")
        if path == "/api/health":
            h = health()
            return self.send(200 if h["ok"] else 503, h, cache="no-store")
        if path == "/api/status":
            return self.send(200, status(), cache="no-store")
        if path == "/api/update/check":
            if not GH_REPO:
                return self.send(400, {"error": "Changelog needs GitHub updates"})
            try:
                return self.send(200, check_github(), cache="no-store")
            except Exception as e:
                update_status["error"] = gh_error(e)
                return self.send(502, {"error": update_status["error"]})
        if path == "/api/sets":
            sl = sets_list()
            out = []
            for sid in sl["order"]:
                m = dict(sl["meta"].get(sid, {"id": sid, "name": sid}))
                coll = read_json(sdir(sid, "collection.json"), {})
                m["owned"] = sum(1 for v in coll.values() if (v or {}).get("qty", 0) > 0)
                cards = card_list(sid)
                m["custom"] = len(custom_list(sid))
                size = binder_size(sid)
                m["count"] = size if size is not None else m.get("total", 0) + m["custom"]
                m["images"] = sid in img_jobs
                if size is not None:
                    have, want = pictures_saved(sid, (cards or []) + extra_list(sid))
                    m["pics"] = {"saved": have, "total": want}
                    m["totals"] = set_totals(sid)
                out.append(m)
            return self.send(200, {"sets": out, "removed": removed_sets(), "keepDays": KEEP_REMOVED_DAYS}, cache="no-store")
        if path == "/api/pokedex":
            idx = dex_index()
            if dex_stale(idx):
                start_dex_index()
            out = {"ready": bool(idx), "building": dex_job["running"], "done": dex_job["done"],
                   "total": dex_job["total"], "error": dex_job["error"], "list": []}
            if idx:
                out["list"] = sorted(({"dex": int(d), "name": nm, "count": len(idx["cards"].get(d, []))}
                                      for d, nm in (idx.get("names") or {}).items()), key=lambda x: x["dex"])
            return self.send(200, out, cache="no-store")
        if path == "/api/shows":
            st = shows_state()
            keep = shows_keep_from()   # between weekly scans, shows older than yesterday drop off the list each day
            return self.send(200, {"shows": sorted((tidy_show(x) for x in st["shows"].values() if x["date"] >= keep),
                                                   key=lambda s: (s["date"], s["name"])),
                                   "areas": st["areas"], "auto": st["auto"], "scanned": st.get("scanned", ""),
                                   "firstScan": st.get("firstScan", ""), "error": st.get("error", ""), "running": shows_job["running"],
                                   "done": shows_job["done"], "total": shows_job["total"],
                                   "today": today_local()}, cache="no-store")
        if path == "/api/changelog":
            return self.send(200, changelog(), cache="no-store")
        if path == "/api/progress":
            # everything the server is working on, for the loading bars
            imgs = {sid: dict(v) for sid, v in list(img_jobs.items()) if isinstance(v, dict)}
            return self.send(200, {"prices": job, "images": imgs, "pokedex": dex_job, "shows": shows_job},
                             cache="no-store")
        if path == "/api/catalog":
            return self.send(200, {"sets": catalog()}, cache="no-store")
        if path == "/api/find":
            q = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("q") or [""])[0]
            return self.send(200, find(q[:120]), cache="no-store")
        m = re.fullmatch(rf"/api/find/set/({SID_RE})", path)
        if m:
            try:
                return self.send(200, find_set(m.group(1)), cache="no-store")
            except ValueError as e:
                return self.send(404, {"error": str(e)})
        if path == "/api/refresh":
            return self.send(200, job, cache="no-store")
        if path == "/api/settings":
            st = get_settings()
            out = {k: st[k] for k in ("auto", "time", "tz", "slots")}
            out["backup"] = bool(st.get("backup", True))
            out["serverName"] = (st.get("serverName") or "").strip()
            out["otherHosts"] = list(st.get("otherHosts") or [])
            ls = st.get("lastSync") or {}
            out["lastSync"] = {"at": ls.get("at", ""), "count": len(ls.get("added") or []), "undone": ls.get("undone", "")} if ls else None
            out["refreshAll"] = bool(st.get("refreshAll"))
            out["showBinders"] = list(st.get("showBinders") or [])
            out["psa"] = bool((st.get("psaToken") or "").strip())   # only whether it's set; the code itself never leaves the server
            out["options"] = {"raw": RAW_CONDS, "graders": GRADERS, "grades": GRADES}
            out["next"] = next_run(st).isoformat() if st["auto"] else ""
            out["lastAuto"] = st.get("lastAuto", "")
            return self.send(200, out, cache="no-store")
        if path == "/api/spending":
            try:
                return self.send(200, spending(), cache="no-store")
            except Exception as e:
                return self.send(500, {"error": f"Couldn't work out spending: {e}"})
        m = re.fullmatch(rf"/api/set/({SID_RE})/history", path)
        if m:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            card = (q.get("card") or [""])[0]
            if card:   # one card's chart
                if not re.fullmatch(NUM_RE, card):
                    return self.send(400, {"error": "bad card"})
                return self.send(200, {"card": card, "points": card_series(m.group(1), card),
                                       "cond": card_cond_series(m.group(1), card), "sales": card_sales(m.group(1), card)},
                                 cache="no-store")
            return self.send(200, read_json(sdir(m.group(1), "history.json"), {}), cache="no-store")
        if path == "/api/habit":   # what you usually pay vs. the price, for the vendor price check
            return self.send(200, pay_habit(), cache="no-store")
        m = re.fullmatch(rf"/api/set/({SID_RE})/trends", path)
        if m:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            today = (q.get("today") or [""])[0]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", today):
                today = today_local()
            try:
                return self.send(200, set_trends(m.group(1), today), cache="no-store")
            except ValueError:
                return self.send(400, {"error": "bad date"})
        if path == "/api/sellers":
            return self.send(200, {"sellers": all_sellers()}, cache="no-store")
        m = re.fullmatch(r"/api/psa/(\d{1,14})", path)
        if m:
            try:
                return self.send(200, psa_check(m.group(1)), cache="no-store")
            except PsaError as e:
                return self.send(e.code, {"error": str(e)})
        m = re.fullmatch(r"/api/psa/(\d{5,12})/(front|back)\.jpg", path)
        if m:
            try:
                f = psa_picture(m.group(1), m.group(2))
            except Exception as e:
                log(f"PSA picture {m.group(1)}: {e}")
                f = None
            return self.send_file(f, "image/jpeg") if f else self.send(404, b"not found", "text/plain")
        if path == "/api/show":
            return self.send(200, show_data(), cache="no-store")
        if path == "/api/home":
            return self.send(200, home_data(), cache="no-store")
        if path == "/api/covernums":   # Pokédex numbers for the binder covers: ?c=neo4-1,neo4-107
            q = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("c") or [""])[0]
            gids = [g for g in q.split(",") if re.fullmatch(NUM_RE, g)]
            return self.send(200, {"dex": card_dex(gids)})
        m = re.fullmatch(rf"/api/set/({SID_RE})/dexnums", path)
        if m:   # Pokédex numbers for a binder's cards, for the Pages view's "Pokédex number" order
            sid = m.group(1)
            if not self.in_binder(sid):
                return self.send(404, {"error": "Set not in binder"})
            idx = card_index()
            if not idx:
                return self.send(200, {"ready": False, "dex": {}}, cache="no-store")
            multi, out = is_multi(sid), {}
            for c in set_cards(sid):
                if c.get("custom"):
                    continue
                row = idx["by"].get(c["n"] if (multi or c.get("extra")) else f"{sid}-{c['n']}")
                if row and len(row) > 7 and row[7]:
                    out[c["n"]] = row[7]
            return self.send(200, {"ready": True, "dex": out}, cache="no-store")
        m = re.fullmatch(rf"/api/set/({SID_RE})/state", path)
        if m:
            sid = m.group(1)
            if not self.in_binder(sid):
                return self.send(404, {"error": "Set not in binder"})
            try:
                cards = set_cards(sid)
            except Exception as e:
                return self.send(502, {"error": f"Couldn't load the card list: {e}"})
            with lock:
                body = {"set": sets_list()["meta"].get(sid, {}), "cards": cards,
                        "collection": read_json(sdir(sid, "collection.json"), {}),
                        "prices": read_json(sdir(sid, "prices.json"), {}), "slots": set_slots(sid),
                        "shop": read_json(sdir(sid, "shop.json"), {}),
                        "layout": read_json(sdir(sid, "layout.json"), None)}
            return self.send(200, body, cache="no-store")
        m = re.fullmatch(rf"/set/({SID_RE})/logo\.png", path)
        if m:
            got = set_logo(m.group(1))
            if not got:
                return self.send(404, b"not found", "text/plain")
            return self.send_file(got, "image/png")
        m = re.fullmatch(rf"/set/({SID_RE})/sprite\.png", path)
        if m:
            return self.send_file(sdir(m.group(1), "sprite.png"), "image/png")
        m = re.fullmatch(rf"/set/({SID_RE})/img/({NUM_RE})\.png", path)
        if m:
            full = "full=1" in (self.path.split("?") + [""])[1]
            got = card_image(m.group(1), m.group(2), full) if (self.in_binder(m.group(1)) or os.path.isdir(sdir(m.group(1)))) else None
            if not got:
                return self.send(404, b"not found", "text/plain")
            return self.send_file(got, "image/png")
        m = re.fullmatch(rf"/set/({SID_RE})/photo/({NUM_RE})(?:/(back))?", path)
        if m:
            name = m.group(2) + ("_back" if m.group(3) else "")
            meta = read_json(sdir(m.group(1), "photos", name + ".json"), {})
            ctype = meta.get("type", "image/jpeg")
            return self.send_file(sdir(m.group(1), "photos", name), ctype if ctype in PHOTO_TYPES else "application/octet-stream", "no-cache")
        self.send(404, b"not found", "text/plain")

    def do_PUT(self):
        if self.blocked(True):
            return
        if self.path == "/api/settings":
            return self.do_PUT_settings()
        if self.path == "/api/shows":
            return self.do_PUT_shows()
        if self.path == "/api/sets/order":
            return self.do_PUT_set_order()
        m = re.fullmatch(rf"/api/sets/({SID_RE})/name", self.path)
        if m:
            try:
                return self.send(200, rename_own(m.group(1), json.loads(self.body(4096) or b"{}").get("name")))
            except (ValueError, AttributeError) as e:
                return self.send(400, {"error": str(e) or "Couldn't rename"})
        m = re.fullmatch(rf"/api/set/({SID_RE})/layout", self.path)
        if m:
            if not self.in_binder(m.group(1)):
                return self.send(400, {"error": "That binder isn't here"})
            try:
                raw = json.loads(self.body(256 * 1024) or b"{}")
                assert isinstance(raw, dict)
                return self.send(200, save_layout(m.group(1), raw))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            except Exception:
                return self.send(400, {"error": "Couldn't save the layout"})
        m = re.fullmatch(rf"/api/set/({SID_RE})/slots", self.path)
        if m:
            return self.do_PUT_slots(m.group(1))
        m = re.fullmatch(rf"/api/set/({SID_RE})/custom/(c\d{{1,5}})", self.path)
        if m:
            if not self.in_binder(m.group(1)):
                return self.send(400, {"error": "That binder isn't here"})
            try:
                return self.send(200, save_custom(m.group(1), m.group(2), json.loads(self.body(8192) or b"{}")))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        m = re.fullmatch(rf"/api/set/({SID_RE})/shop", self.path)
        if m:
            return self.do_PUT_shop(m.group(1))
        m = re.fullmatch(rf"/api/set/({SID_RE})/card/({NUM_RE})", self.path)
        raw = self.body(64 * 1024) if m else None
        if not m or raw is None or not self.in_binder(m.group(1)):
            return self.send(400, {"error": "bad request"})
        try:
            rec = json.loads(raw)
            assert isinstance(rec, dict)
        except Exception:
            return self.send(400, {"error": "bad json"})
        sid, n = m.groups()
        with lock:
            collection_put(sid, n, rec)
        self.send(200, {"ok": True})

    def do_PUT_shows(self):
        """Card show options: the towns to look in and whether to scan every week."""
        try:
            new = json.loads(self.body(4096) or b"{}")
            assert isinstance(new, dict)
            if "areas" in new:
                areas = [str(a).strip() for a in new["areas"] if str(a).strip()]
                assert 1 <= len(areas) <= 40 and all(len(a) <= 40 and re.fullmatch(r"[A-Za-z .'\-]+", a) for a in areas)
        except Exception:
            return self.send(400, {"error": "Use town names separated by commas, like Richmond, Midlothian"})
        with lock:   # read and save together, so a scan finishing at the same moment can't undo this
            st = shows_state()
            if "auto" in new:
                st["auto"] = bool(new["auto"])
            if "areas" in new:
                st["areas"] = list(dict.fromkeys(areas))
            write_json(SHOWS_FILE, st)
        return self.send(200, {"ok": True})

    def do_PUT_shop(self, sid):
        """Save the shopping list order: a sort mode, plus your own card order for "My order"."""
        if not self.in_binder(sid):
            return self.send(404, {"error": "Set not in binder"})
        try:
            new = json.loads(self.body(64 * 1024) or b"{}")
            mode = new.get("mode")
            order = new.get("order") or []
            assert mode in ("lo", "hi", "num", "mine")
            assert isinstance(order, list) and len(order) <= 1000
            assert all(isinstance(n, str) and re.fullmatch(NUM_RE, n) for n in order)
            upg = new.get("upg") or {"from": ["HP", "DMG"], "to": "LP"}
            assert isinstance(upg.get("from"), list) and all(c in RAW_CONDS for c in upg["from"]) and upg.get("to") in RAW_CONDS
        except Exception:
            return self.send(400, {"error": "Invalid shopping list order"})
        with lock:
            write_json(sdir(sid, "shop.json"), {"mode": mode, "order": list(dict.fromkeys(order)),
                                                "upg": {"from": list(dict.fromkeys(upg["from"])), "to": upg["to"]}})
        return self.send(200, {"ok": True})

    def do_PUT_set_order(self):
        """Save the order of binders in the sets menu. Must list exactly the binders you have."""
        try:
            new = json.loads(self.body(16 * 1024) or b"{}").get("order")
            assert isinstance(new, list) and all(isinstance(x, str) for x in new)
        except Exception:
            return self.send(400, {"error": "Invalid order"})
        with lock:
            sl = sets_list()
            if sorted(new) != sorted(sl["order"]) or len(set(new)) != len(new):
                return self.send(409, {"error": "Your binders changed. Reload and try again"})
            sl["order"] = new
            write_json(SETS_FILE, sl)
        return self.send(200, {"ok": True})

    def do_PUT_slots(self, sid):
        """Save one binder's price options, then recalculate its prices from stored sales."""
        if not self.in_binder(sid):
            return self.send(404, {"error": "Set not in binder"})
        try:
            new = json.loads(self.body(4096) or b"{}")
            assert isinstance(new, dict)
        except Exception:
            return self.send(400, {"error": "Invalid price options"})
        try:
            slots = clean_slots(new.get("slots"))
        except ValueError as e:
            return self.send(400, {"error": str(e) or "Invalid price options"})
        except Exception:
            return self.send(400, {"error": "Invalid price options"})
        with lock:
            write_json(sdir(sid, "slots.json"), slots)
        return self.send(200, {"ok": True, "slots": slots, "needsRefresh": recompute_prices([sid])})

    def do_PUT_settings(self):
        raw = self.body(4096)
        try:
            new = json.loads(raw or b"{}")
            assert isinstance(new, dict)
            # read and save together, so the scheduler saving "last run" at the same moment can't undo this
            with lock:
                st = read_json(SETTINGS, {})
                if "auto" in new:
                    st["auto"] = bool(new["auto"])
                if "time" in new:
                    assert re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", new["time"])
                    st["time"] = new["time"]
                if "tz" in new:
                    assert re.fullmatch(r"[A-Za-z_]+(/[A-Za-z_+\-]+){0,2}", new["tz"])
                    st["tz"] = new["tz"]
                if "offset" in new:
                    st["offset"] = int(new["offset"])
                slots_changed = "slots" in new or "backup" in new
                if "slots" in new:
                    st["slots"] = clean_slots(new["slots"])
                if "backup" in new:
                    st["backup"] = bool(new["backup"])
                if "refreshAll" in new:
                    st["refreshAll"] = bool(new["refreshAll"])
                if "serverName" in new:
                    name = re.sub(r"\s+", " ", str(new["serverName"] or "")).strip()
                    if len(name) > 24 or not re.fullmatch(r"[\w .'\-]*", name):
                        raise ValueError("Use letters, numbers, spaces, dots or dashes for the server name (24 at most)")
                    st["serverName"] = name
                if "otherHosts" in new:
                    st["otherHosts"] = clean_hosts(new["otherHosts"])
                if "psaToken" in new:   # PSA slab check access code
                    tok = re.sub(r"^\s*bearer\s+", "", str(new["psaToken"] or "").strip().strip('"\''), flags=re.I).strip()
                    if len(tok) > 3000 or not re.fullmatch(r"[\w\-.~+/=]*", tok):
                        raise ValueError("That doesn't look like a PSA access code. Copy the whole code from psacard.com/publicapi")
                    st["psaToken"] = tok
                    psa_state["denied"] = 0   # a new code gets tried right away
                if "showBinders" in new:   # card show mode: the binders you're working on
                    order = sets_list()["order"]
                    st["showBinders"] = [x for x in dict.fromkeys(new["showBinders"] or []) if isinstance(x, str) and x in order]
                # a new time today shouldn't be skipped just because today's run already happened earlier
                if "time" in new:
                    merged = dict(DEFAULT_SETTINGS); merged.update(st)
                    now = local_now(merged)
                    h, m = map(int, merged["time"].split(":"))
                    if now < now.replace(hour=h, minute=m, second=0, microsecond=0):
                        st["lastAuto"] = ""
                write_json(SETTINGS, st)
        except Exception as e:
            return self.send(400, {"error": str(e) if isinstance(e, ValueError) and str(e) else "Invalid settings"})
        merged = get_settings()
        load_other_hosts()
        out = {"ok": True, "next": next_run(merged).isoformat() if merged["auto"] else ""}
        if slots_changed:
            out["needsRefresh"] = recompute_prices()
        return self.send(200, out)

    def do_DELETE(self):
        if self.blocked(True):
            return
        if self.path == "/api/icon":
            for f in (ICON_FILE, ICON_FILE + ".json"):
                if os.path.exists(f):
                    os.remove(f)
            return self.send(200, {"ok": True})
        m = re.fullmatch(rf"/api/set/({SID_RE})/custom/(c\d{{1,5}})", self.path)
        if m:
            if not self.in_binder(m.group(1)):
                return self.send(400, {"error": "That binder isn't here"})
            try:
                delete_custom(m.group(1), m.group(2))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            return self.send(200, {"ok": True})
        m = re.fullmatch(rf"/api/set/({SID_RE})/cards/({NUM_RE})", self.path)
        if m:
            if not self.in_binder(m.group(1)):
                return self.send(400, {"error": "That binder isn't here"})
            try:
                remove_card(m.group(1), m.group(2))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            return self.send(200, {"ok": True})
        m = re.fullmatch(rf"/api/sets/({SID_RE})", self.path)
        if not m:
            return self.send(400, {"error": "bad request"})
        remove_set(m.group(1))
        self.send(200, {"ok": True})

    def do_POST(self):
        if self.blocked(True):
            return
        path = self.path.split("?")[0]
        if path == "/api/sync":   # the phone app sends what was added while offline
            try:
                new = json.loads(self.body(256 * 1024) or b"{}")
                assert isinstance(new, dict) and isinstance(new.get("changes"), list) and len(new["changes"]) <= 500
            except Exception:
                return self.send(400, {"error": "Invalid sync"})
            try:
                return self.send(200, dict(apply_sync(new["changes"]), ok=True))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        if path == "/api/sync/undo":
            try:
                return self.send(200, dict(undo_sync(), ok=True))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        if path == "/api/restore":
            size = int(self.headers.get("Content-Length") or 0)
            if size <= 0 or size > MAX_RESTORE:
                return self.send(413, {"error": "That file is empty or too big"})
            fd, tmp = tempfile.mkstemp(suffix=".zip", dir=APP)
            try:
                with os.fdopen(fd, "wb") as f:
                    left = size
                    while left:
                        chunk = self.rfile.read(min(left, 1 << 20))
                        if not chunk:
                            break
                        f.write(chunk)
                        left -= len(chunk)
                count, safety = restore_backup(tmp)
            except Busy as e:
                return self.send(409, {"error": str(e)})
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            except Exception as e:
                return self.send(500, {"error": f"Restore failed: {e}"})
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            return self.send(200, {"ok": True, "files": count, "safety": safety})
        if path == "/api/backups/restore":
            raw = self.body(4096)
            try:
                name = json.loads(raw or b"{}").get("name", "")
                assert AUTO_NAME_RE.fullmatch(name) and os.path.isfile(os.path.join(BACKUPS, name))
            except Exception:
                return self.send(400, {"error": f"That backup isn't on {srv_name()} any more"})
            try:
                count, safety = restore_backup(os.path.join(BACKUPS, name))
            except Busy as e:
                return self.send(409, {"error": str(e)})
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            except Exception as e:
                return self.send(500, {"error": f"Restore failed: {e}"})
            return self.send(200, {"ok": True, "files": count, "safety": safety})
        m_cu = re.fullmatch(rf"/api/set/({SID_RE})/custom", path)
        if m_cu:
            sid = m_cu.group(1)
            if not self.in_binder(sid):
                return self.send(400, {"error": "That binder isn't here"})
            try:
                return self.send(200, save_custom(sid, None, json.loads(self.body(8192) or b"{}")))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        m_imp = re.fullmatch(rf"/api/set/({SID_RE})/import", path)
        if m_imp:
            sid = m_imp.group(1)
            if not self.in_binder(sid):
                return self.send(400, {"error": "That binder isn't here"})
            raw = self.body(MAX_IMPORT)
            if not raw:
                return self.send(413, {"error": "That file is empty or too big (10 MB max)"})
            apply = "apply=1" in (self.path.split("?") + [""])[1]
            try:
                rows = read_sheet(raw)
                plan = import_plan(sid, rows)
                if apply:
                    plan["backup"] = apply_import(sid, plan)
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            except Exception as e:
                log(f"{sid}: import failed: {e}")
                return self.send(500, {"error": f"Import failed: {e}"})
            return self.send(200, plan)
        if path == "/api/icon":
            ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if ctype not in ICON_TYPES:
                return self.send(400, {"error": "Use a PNG, JPG, WebP, GIF or ICO image"})
            raw = self.body(MAX_ICON)
            if raw is None:
                return self.send(413, {"error": "That image is too big (2 MB max)"})
            with lock:
                with open(ICON_FILE, "wb") as f:
                    f.write(raw)
                write_json(ICON_FILE + ".json", {"type": ctype})
            return self.send(200, {"ok": True, "v": int(time.time())})
        m_pic = re.fullmatch(rf"/api/sets/({SID_RE})/pictures", path)
        if m_pic:
            if m_pic.group(1) not in sets_list()["order"]:
                return self.send(404, {"error": "No such binder"})
            start_images(m_pic.group(1), now=True)
            return self.send(200, {"started": True})
        m_buy = re.fullmatch(rf"/api/set/({SID_RE})/card/({NUM_RE})/buy", path)
        if m_buy:   # card show mode: add one copy you just bought, from any screen
            try:
                body = json.loads(self.body(4096) or b"{}")
                assert isinstance(body, dict)
                sid, n, purchase = clean_sync_change({"sid": m_buy.group(1), "n": m_buy.group(2),
                                                      "purchase": body.get("purchase"), "cond": body.get("cond")})
                if sid not in sets_list()["order"]:
                    raise ValueError("That binder isn't on the server any more")
                with lock:
                    added = add_one_purchase(sid, n, purchase)
            except (ValueError, AssertionError) as e:
                return self.send(400, {"error": str(e) or "bad request"})
            except Exception:
                return self.send(400, {"error": "bad request"})
            return self.send(200, {"ok": True, "added": added})
        m_rs = re.fullmatch(rf"/api/sets/({SID_RE})/restore", path)
        if m_rs:
            try:
                return self.send(200, restore_set(m_rs.group(1)))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        if path == "/api/sets/own":
            try:
                return self.send(200, add_own(json.loads(self.body(4096) or b"{}").get("name")))
            except (ValueError, AttributeError) as e:
                return self.send(400, {"error": str(e) or "Couldn't make the binder"})
        m_add = re.fullmatch(rf"/api/set/({SID_RE})/cards", path)
        if m_add:
            sid = m_add.group(1)
            if not self.in_binder(sid):
                return self.send(400, {"error": "That binder isn't here"})
            try:
                gid = json.loads(self.body(4096) or b"{}").get("id", "")
                assert isinstance(gid, str) and re.fullmatch(NUM_RE, gid)
            except Exception:
                return self.send(400, {"error": "bad request"})
            try:
                return self.send(200, add_card(sid, gid))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        if path == "/api/sets":
            raw = self.body(4096)
            try:
                body = json.loads(raw or b"{}")
                sid, keep = body.get("id", ""), body.get("keep")
                assert re.fullmatch(SID_RE, sid) and keep in (None, True, False)
                meta = add_set_again(sid, keep)
            except SavedCards as e:
                return self.send(409, {"error": str(e), "saved": e.saved})
            except urllib.error.URLError as e:
                return self.send(502, {"error": f"Couldn't download the card list: {e}"})
            except Exception as e:
                return self.send(400, {"error": str(e) or "Couldn't add that set"})
            return self.send(200, meta)
        if path == "/api/update":
            # install the latest version (from GitHub, or the updates folder)
            if not GH_REPO and not os.path.isdir(UPDATES):
                return self.send(400, {"error": "Updates aren't set up"})
            try:
                with big_job("an update") as slot:
                    installed = install_from_github() if GH_REPO else install_files(UPDATES, "update from the updates folder")
                    restarting = any(n.endswith(".py") for n in installed)
                    slot["keep"] = restarting   # keep other big jobs out until the binder restarts on the new version
            except Busy as e:
                return self.send(409, {"error": str(e)})
            except Exception as e:
                return self.send(502, {"error": gh_error(e)})
            self.send(200, {"installed": installed, "restarting": restarting})
            if restarting:
                threading.Thread(target=restart_self, args=(1,), daemon=True).start()
            return
        if path == "/api/rollback":
            raw = self.body(4096)
            try:
                vid = json.loads(raw or b"{}").get("id", "")
                with big_job("a rollback") as slot:
                    installed = rollback(vid)
                    restarting = any(n.endswith(".py") for n in installed)
                    slot["keep"] = restarting
            except Busy as e:
                return self.send(409, {"error": str(e)})
            except Exception as e:
                return self.send(400, {"error": str(e) or "Couldn't roll back"})
            self.send(200, {"installed": installed, "restarting": restarting})
            if restarting:
                threading.Thread(target=restart_self, args=(1,), daemon=True).start()
            return
        if path == "/api/shows/scan":
            if not shows_job["running"]:
                threading.Thread(target=scan_shows, args=("manual",), daemon=True).start()
                time.sleep(0.2)
            return self.send(200, {"running": shows_job["running"]})
        if path == "/api/refresh":
            raw = self.body(4096)
            try:
                sid = str(json.loads(raw or b"{}").get("set", ""))
            except Exception:
                return self.send(400, {"error": "bad request"})
            if not job["running"] and sid and self.in_binder(sid):
                threading.Thread(target=refresh_prices, args=(sid, "manual"), daemon=True).start()
                time.sleep(0.2)
            return self.send(200, job)
        m = re.fullmatch(rf"/api/set/({SID_RE})/photo/({NUM_RE})(?:/(back))?", path)
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if not m or not self.in_binder(m.group(1)):
            return self.send(400, {"error": "bad request"})
        if ctype not in PHOTO_TYPES:
            return self.send(400, {"error": "Use a JPG, PNG, WebP, GIF or HEIC photo"})
        raw = self.body(MAX_PHOTO)
        if raw is None:
            return self.send(413, {"error": "too large"})
        sid, n, back = m.groups()
        name = n + ("_back" if back else "")
        os.makedirs(sdir(sid, "photos"), exist_ok=True)
        with open(sdir(sid, "photos", name), "wb") as f:
            f.write(raw)
        write_json(sdir(sid, "photos", name + ".json"), {"type": ctype})
        self.send(200, {"v": int(time.time())})


def _safe(fn):
    """Any unexpected error in a request still gets an answer (instead of the page waiting on nothing),
    and the details go to the container log."""
    def run(self):
        self.replied = False
        try:
            return fn(self)
        except (BrokenPipeError, ConnectionResetError):
            pass   # the browser went away
        except Exception as e:
            log(f"{self.command} {self.path} failed:\n{traceback.format_exc().rstrip()}")
            if not self.replied:
                try:
                    self.send(500, {"error": f"Something went wrong on {srv_name()} ({e.__class__.__name__}). The container log has details"})
                except OSError:
                    pass
    return run


for _name in ("do_GET", "do_PUT", "do_POST", "do_DELETE"):
    setattr(Handler, _name, _safe(getattr(Handler, _name)))
