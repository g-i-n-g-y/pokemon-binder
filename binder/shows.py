"""Local card shows.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

# ---------- local card shows (from treasurehunter.show) ----------

SHOWS_FILE = os.path.join(DATA, "shows.json")
TH = "https://www.treasurehunter.show"
DEFAULT_AREAS = ["Richmond", "Midlothian", "Chesterfield", "Chester", "Glen Allen", "Henrico", "Short Pump",
                 "Mechanicsville", "Ashland", "Petersburg", "Colonial Heights", "Hopewell", "Powhatan", "Sandston"]
SHOW_RE = re.compile(r'/show/([a-z0-9-]+?)-va-(\d{4}-\d{2}-\d{2})(?=["\'#?/])')
TCG_RE = re.compile(r"pok[eé]?mon|pokmon|\btcg\b|trading card game", re.I)


def area_slug(name):
    return slugify(name)


def shows_state():
    st = read_json(SHOWS_FILE, {})
    st.setdefault("shows", {})
    st.setdefault("areas", DEFAULT_AREAS)
    st.setdefault("auto", True)
    return st


def tidy_show(rec):
    """Drop the town and date the site adds to every title and description (the panel already shows them)."""
    name = re.sub(r"\s+[—–-]\s+[^—–]*,\s*(?:VA|Virginia)\b[^—–]*$", "", rec.get("name", "")).strip()
    desc = re.sub(r"^.*?\bin [^.]*?,\s*Virginia on [A-Z][a-z]+\.? \d{1,2}, \d{4}\.\s*", "", rec.get("desc", "")).strip()
    return dict(rec, name=name or rec.get("name", ""), desc=desc)


def show_details(url):
    """Name, description and image from one show's page (only fetched the first time it's seen)."""
    _, html = pc_get(url)
    def meta(prop):
        m = re.search(rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']*)', html, re.I) or \
            re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']{prop}["\']', html, re.I)
        return unescape(m.group(1)).strip() if m else ""
    title = meta("og:title")
    if not title:
        m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
        title = unescape(m.group(1)).strip() if m else ""
    title = re.split(r"\s+[|·–-]\s+Treasure Hunter", title)[0].strip()
    return {"name": title, "desc": meta("og:description") or meta("description")}


def scan_shows(reason="manual"):
    """Read the Virginia show pages for each area, keep shows in those towns, remember new ones."""
    with job_lock:
        if shows_job["running"]:
            return False
        shows_job.update(running=True, error="", done=0, total=0)
    try:
        st = shows_state()
        areas = [a for a in st["areas"] if area_slug(a)]
        slugs = {area_slug(a): a for a in areas}
        pages = [f"{TH}/shows/virginia"] + [f"{TH}/shows/virginia/{s}" for s in slugs]
        found, ok = {}, 0
        shows_job["total"] = len(pages)
        for i, url in enumerate(pages):
            shows_job["done"] = i
            try:
                _, html = pc_get(url)
                ok += 1
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    log(f"card shows: {url}: {e}")
                continue
            except Exception as e:
                log(f"card shows: {url}: {e}")
                continue
            for slug, d in SHOW_RE.findall(html):
                town = next((s for s in sorted(slugs, key=len, reverse=True) if slug.endswith("-" + s) or slug == s), None)
                if town:
                    found[f"{slug}-va-{d}"] = {"town": slugs[town], "date": d, "slug": slug[: -len(town)].strip("-")}
            time.sleep(1)
        if not ok:
            raise RuntimeError("couldn't reach treasurehunter.show")
        now = now_iso()
        shows = st["shows"]
        new = 0
        shows_job.update(done=len(pages), total=len(pages) + sum(1 for k in found if k not in shows))
        for key, f in found.items():
            if key in shows:
                shows[key]["seen"] = now
                continue
            url = f"{TH}/show/{key}"
            rec = {"url": url, "date": f["date"], "town": f["town"], "first": now, "seen": now,
                   "name": f["slug"].replace("-", " ").title(), "desc": ""}
            try:
                det = show_details(url)
                rec["name"] = det["name"] or rec["name"]
                rec["desc"] = det["desc"][:300]
                time.sleep(1)
            except Exception as e:
                log(f"card shows: {url}: {e}")
            rec["tcg"] = bool(TCG_RE.search(rec["name"] + " " + rec["desc"] + " " + key))
            shows[key] = rec
            new += 1
            shows_job["done"] += 1
        keep = shows_keep_from()
        with lock:
            cur = shows_state()   # newest copy, so town or weekly-scan changes made during the scan are kept
            cur["shows"] = {k: v for k, v in shows.items() if v["date"] >= keep}   # drop shows older than yesterday
            cur.setdefault("firstScan", now)   # shows found on the very first scan aren't marked new
            cur.update(scanned=now, lastNew=new, error="")
            write_json(SHOWS_FILE, cur)
        log(f"Card shows scan ({reason}): {len(found)} in your area, {new} new.")
    except Exception as e:
        shows_job["error"] = str(e)
        with lock:
            st = shows_state()
            st["error"] = str(e)
            write_json(SHOWS_FILE, st)
        log(f"Card shows scan failed: {e}")
    finally:
        shows_job["running"] = False
    return True


def shows_keep_from():
    """Shows stay listed through the day after they happen, so a show on the day a scan runs (or one that ran
    late into the night) doesn't vanish. Older ones are dropped."""
    return (local_now(get_settings()) - timedelta(days=1)).strftime("%Y-%m-%d")


def shows_due():
    st = shows_state()
    if not st.get("auto"):
        return False
    last = st.get("scanned", "")
    try:
        age = time.time() - datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return True
    return age > 7 * DAY
