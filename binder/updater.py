"""Updates: checking GitHub, test-starting a new version, installing, rolling back.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

UPDATES = os.environ.get("BINDER_UPDATES", "/updates")
APP_FILE_RE = re.compile(r"[A-Za-z0-9_\-]+(?:/[A-Za-z0-9_\-]+)*\.(?:py|html|js|css|woff2|png|svg|json|txt)")
GH_REPO = os.environ.get("GITHUB_REPO", "g-i-n-g-y/pokemon-binder")
GH_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
VERSION_FILE = os.path.join(APP, ".version.json")   # {commit, subject, date, installed, paused}
PREVIOUS = os.path.join(APP, "previous")            # previous/<stamp>/{server.py, index.html, meta.json}
KEEP_VERSIONS = 3
update_status = {"source": "", "checked": "", "error": ""}


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def files_of(server_path):
    """The program files the server.py at `server_path` needs (its APP_FILES line), safest names only.
    Versions from before v3.0 have no such line and use server.py and index.html."""
    try:
        with open(server_path, encoding="utf-8", errors="ignore") as f:
            m = re.search(r"^APP_FILES\s*=\s*(\([^)]*\))", f.read(), re.M)
        names = tuple(ast.literal_eval(m.group(1))) if m else ("server.py", "index.html")
    except (OSError, ValueError, SyntaxError):
        names = ("server.py", "index.html")
    if "server.py" not in names or not all(isinstance(n, str) and APP_FILE_RE.fullmatch(n) for n in names):
        raise RuntimeError("The new version's file list looks wrong, so nothing was installed")
    return names


def copy_into(src_root, dst_root, names):
    for name in names:
        dst = os.path.join(dst_root, *name.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(src_root, *name.split("/")), dst)


def current_version():
    return read_json(VERSION_FILE, {})


def same_file(a, b):
    try:
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False


def file_version(path):
    """The APP_VERSION written in a server.py file, or "" for versions from before numbering."""
    try:
        with open(path) as f:
            m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', f.read(), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


def split_subject(subject):
    """'v1.2: Add photos' -> ('1.2', 'Add photos'); other subjects -> ('', subject)."""
    m = re.match(r"v(\d+(?:\.\d+)+)\s*[:\-]\s*(.*)", subject or "")
    return (m.group(1), m.group(2)) if m else ("", subject or "")


def server_ok(path):
    """True if the server.py at `path` has no syntax errors."""
    try:
        with open(path) as f:
            compile(f.read(), path, "exec")
        return True
    except SyntaxError as e:
        log(f"Update skipped: the new server.py has an error on line {e.lineno}. Still running the current version.")
        return False


def trial_run(folder):
    """Start the new version on a spare port, with a copy of your data, and check that its pages answer.
    Nothing it does touches the real binder. Returns "" if it works, or what went wrong."""
    with open(os.path.join(folder, "server.py"), encoding="utf-8", errors="ignore") as f:
        if "BINDER_TRIAL" not in f.read():
            return ""   # versions from before v2.20 can't be test-started; the syntax check still ran
    tmp = tempfile.mkdtemp(prefix=".trial-", dir=APP)
    proc = logf = None
    try:
        copy_into(folder, tmp, files_of(os.path.join(folder, "server.py")))
        # a copy of the small data files only (no card pictures or photos)
        for root, dirs, files in os.walk(DATA):
            dirs[:] = [d for d in dirs if d not in ("images", "photos") and not d.startswith("pre-sqlite")]
            for fn in files:
                if fn.endswith(".json"):
                    dst = os.path.join(tmp, "data", os.path.relpath(os.path.join(root, fn), DATA))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copyfile(os.path.join(root, fn), dst)
        if os.path.exists(DB_FILE):   # a consistent copy of the database, made while the binder keeps running
            os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
            dst = sqlite3.connect(os.path.join(tmp, "data", "binder.db"))
            try:
                with db_lock:
                    db().backup(dst)
            finally:
                dst.close()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        logf = open(os.path.join(tmp, "trial.log"), "w+")
        proc = subprocess.Popen([sys.executable, "-u", os.path.join(tmp, "server.py")], cwd=tmp, stdout=logf,
                                stderr=subprocess.STDOUT, env=dict(os.environ, BINDER_PORT=str(port), BINDER_TRIAL="1"))
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        order = sets_list()["order"]
        pages = ["/", "/api/sets", "/api/settings", "/api/version", "/api/spending", "/api/changelog"] + \
                [f"/api/set/{sid}/state" for sid in order[:3]]

        def status(page):
            try:
                with opener.open(f"http://127.0.0.1:{port}{page}", timeout=15) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                return e.code

        deadline = time.time() + 25
        while True:   # wait for it to start
            if proc.poll() is not None:
                break
            try:
                status("/")
                break
            except (urllib.error.URLError, OSError):
                if time.time() > deadline:
                    break
                time.sleep(0.5)
        problem = ""
        if proc.poll() is not None:
            problem = "it stopped right after starting"
        else:
            for page in pages:
                try:
                    code = status(page)
                except Exception as e:
                    problem = f"{page} didn't answer ({e.__class__.__name__})"
                    break
                if code >= 500 and code != 502:   # 502 = a website it needs is down, not a problem with the app
                    problem = f"{page} gave error {code}"
                    break
        if problem:
            logf.seek(0)
            tail = [ln for ln in logf.read().splitlines() if ln.strip()][-8:]
            log("Update test failed: " + problem + ("\n  " + "\n  ".join(tail) if tail else ""))
        return problem
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if logf:
            logf.close()
        shutil.rmtree(tmp, ignore_errors=True)


def save_current_version():
    """Keep a copy of the running version so it can be rolled back to later (newest 3 are kept)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    dest = os.path.join(PREVIOUS, stamp)
    os.makedirs(dest, exist_ok=False)
    copy_into(APP, dest, [n for n in APP_FILES if os.path.isfile(os.path.join(APP, *n.split("/")))])
    cur = current_version()
    write_json(os.path.join(dest, "meta.json"), {"version": file_version(os.path.join(APP, "server.py")),
                                                  "commit": cur.get("commit", ""), "subject": cur.get("subject", ""),
                                                  "date": cur.get("date", ""), "installed": cur.get("installed", ""),
                                                  "saved": now_iso()})
    for old in list_versions()[KEEP_VERSIONS:]:
        shutil.rmtree(os.path.join(PREVIOUS, old["id"]), ignore_errors=True)


def list_versions():
    """Saved previous versions, newest first."""
    out = []
    if os.path.isdir(PREVIOUS):
        for d in sorted(os.listdir(PREVIOUS), reverse=True):
            meta = read_json(os.path.join(PREVIOUS, d, "meta.json"), None)
            if meta is not None and os.path.isfile(os.path.join(PREVIOUS, d, "server.py")):
                out.append(dict(meta, id=d))
    return out


def install_files(folder, label):
    """Install changed program files from `folder`. Saves the running version first. Returns files installed."""
    if not os.path.isfile(os.path.join(folder, "server.py")):
        return []
    names = files_of(os.path.join(folder, "server.py"))
    missing = [n for n in names if not os.path.isfile(os.path.join(folder, *n.split("/")))]
    if missing:
        raise RuntimeError(f"The new version is missing {', '.join(missing)}, so nothing was installed")
    changed = [n for n in names if not same_file(os.path.join(folder, *n.split("/")), os.path.join(APP, *n.split("/")))]
    if not changed:
        return []
    # skip the whole update if the new version is broken, so you keep a working binder
    broken = [n for n in names if n.endswith(".py") and not server_ok(os.path.join(folder, *n.split("/")))]
    if broken:
        raise RuntimeError("The new version has a mistake in its code, so nothing was installed. You're still on the current version")
    problem = trial_run(folder)
    if problem:
        raise RuntimeError(f"The new version failed a test start ({problem}), so nothing was installed. "
                           "You're still on the current version")
    try:
        auto_backup("before-update")
    except Exception as e:
        log(f"Update skipped: couldn't save a backup first ({e})")
        raise RuntimeError(f"Update skipped because a backup couldn't be saved first: {e}")
    save_current_version()
    # copy everything next to its place first, then swap them in, server.py last
    for name in changed:
        dst = os.path.join(APP, *name.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(folder, *name.split("/")), dst + ".tmp")
    for name in sorted(changed, key=lambda n: n == "server.py"):
        dst = os.path.join(APP, *name.split("/"))
        os.replace(dst + ".tmp", dst)
    log(f"Installed {label}: " + ", ".join(changed))
    return changed


def gh_get(path, accept):
    headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "pokemon-binder"}
    if GH_TOKEN:  # only for a private copy of the repository
        headers["Authorization"] = f"Bearer {GH_TOKEN}"
    req = urllib.request.Request(f"https://api.github.com/repos/{GH_REPO}/{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def gh_json(path):
    return json.loads(gh_get(path, "application/vnd.github+json"))


def gh_error(e):
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 404:
            return "Repository " + GH_REPO + " wasn't found. It may be private"
        if e.code in (403, 429) and not GH_TOKEN:
            return "GitHub's hourly limit for update checks was reached. Try again in an hour"
        if e.code == 401:
            return "GitHub key was rejected (it may have expired)"
        return f"GitHub error {e.code}"
    if isinstance(e, RuntimeError):   # our own message, like "the new version didn't start"
        return str(e)
    return f"Couldn't reach GitHub ({e.__class__.__name__})"


def commit_info(c):
    msg = (c.get("commit") or {}).get("message", "")
    ver, text = split_subject(msg.split("\n")[0][:160])
    return {"sha": c.get("sha", ""), "version": ver, "subject": text,
            "date": ((c.get("commit") or {}).get("committer") or {}).get("date", "")}


def check_github():
    """What's new on GitHub compared with what's installed: {latest, changes, upToDate}."""
    update_status.update(source="github", checked=now_iso(), error="")
    latest = commit_info(gh_json(f"commits/{GH_BRANCH}"))
    ver = current_version()
    cur = ver.get("commit", "")
    if cur and not ver.get("subject"):   # versions installed before changelogs existed: fill in the description
        try:
            info = commit_info(gh_json(f"commits/{cur}"))
            write_json(VERSION_FILE, dict(ver, subject=info["subject"], date=info["date"]))
            ver = current_version()
        except Exception:
            pass
    if cur == latest["sha"]:
        return {"upToDate": True, "latest": latest, "changes": []}
    running = file_version(os.path.join(APP, "server.py"))
    try:   # the version written in the latest server.py, which is what would actually be installed
        m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"',
                      gh_get(f"contents/server.py?ref={latest['sha']}", "application/vnd.github.raw").decode("utf-8", "ignore"), re.M)
        latest["fileVersion"] = m.group(1) if m else ""
    except Exception:
        latest["fileVersion"] = latest["version"]
    if running and latest["fileVersion"] == running:
        return {"upToDate": True, "latest": latest, "changes": []}   # only non-app changes (like the README)
    changes = []
    if cur:
        try:
            cmp = gh_json(f"compare/{cur}...{latest['sha']}")
            if cmp.get("status") in ("ahead", "diverged"):
                changes = [commit_info(c) for c in reversed(cmp.get("commits") or [])]
                changes = [c for c in changes if c["version"]][:15] or changes[:15]
        except Exception:
            changes = []
    if not changes:
        changes = [latest]
    return {"upToDate": False, "latest": latest, "running": running, "changes": changes}


CHANGELOG_CACHE = {"at": 0, "text": "", "error": ""}


def ver_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


def parse_changelog(text):
    """CHANGELOG.md -> [{"v": "2.12", "date": "October 11, 2026", "items": [{"t": text, "sub": [..]}], "notes": [..]}]"""
    entries, cur = [], None
    for line in text.splitlines():
        m = re.match(r"##\s+v(\d+(?:\.\d+)+)\s*(?:\((.*?)\))?\s*$", line)
        if m:
            cur = {"v": m.group(1), "date": m.group(2) or "", "items": [], "notes": []}
            entries.append(cur)
            continue
        if cur is None or not line.strip():
            continue
        m = re.match(r"(\s*)[-*]\s+(.*)", line)
        if m:
            if len(m.group(1)) >= 2 and cur["items"]:
                cur["items"][-1]["sub"].append(m.group(2).strip())
            else:
                cur["items"].append({"t": m.group(2).strip(), "sub": []})
        else:
            cur["notes"].append(line.strip())
    return entries


def changelog():
    """Release notes from GitHub (checked at most once an hour), plus whether a newer version is out."""
    if GH_REPO and time.time() - CHANGELOG_CACHE["at"] > 3600:
        try:
            CHANGELOG_CACHE["text"] = gh_get(f"contents/CHANGELOG.md?ref={GH_BRANCH}", "application/vnd.github.raw").decode("utf-8", "ignore")
            CHANGELOG_CACHE["error"] = ""
        except Exception as e:
            CHANGELOG_CACHE["error"] = gh_error(e)
        CHANGELOG_CACHE["at"] = time.time()
    entries = parse_changelog(CHANGELOG_CACHE["text"])
    latest = entries[0]["v"] if entries else ""
    return {"running": APP_VERSION, "latest": latest, "entries": entries[:40],
            "updateAvailable": bool(latest) and ver_tuple(latest) > ver_tuple(APP_VERSION),
            "repo": GH_REPO, "branch": GH_BRANCH, "error": CHANGELOG_CACHE["error"]}


def install_from_github(sha=None):
    """Download this version's program files at `sha` (default: latest) and install them. Returns files installed."""
    update_status.update(source="github", checked=now_iso(), error="")
    info = commit_info(gh_json(f"commits/{sha or GH_BRANCH}"))
    stage = os.path.join(APP, ".incoming")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage, exist_ok=True)

    def fetch(name):
        dst = os.path.join(stage, *name.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(gh_get(f"contents/{name}?ref={info['sha']}", "application/vnd.github.raw"))

    fetch("server.py")   # first: it says which other files this version needs
    for name in files_of(os.path.join(stage, "server.py")):
        if name != "server.py":
            fetch(name)
    installed = install_files(stage, f"update {info['sha'][:7]} ({info['subject']})")
    # record the version only if its server.py is what's now running
    if same_file(os.path.join(stage, "server.py"), os.path.join(APP, "server.py")):
        write_json(VERSION_FILE, dict(info, commit=info["sha"], installed=now_iso(), paused=False))
    return installed


def rollback(version_id):
    """Reinstall a saved previous version. Pauses automatic updates. Returns files installed."""
    folder = os.path.join(PREVIOUS, version_id)
    meta = read_json(os.path.join(folder, "meta.json"), None)
    if meta is None or not re.fullmatch(r"[0-9-]+", version_id):
        raise ValueError("That version isn't available")
    with open(os.path.join(folder, "server.py"), encoding="utf-8", errors="ignore") as f:
        uses_db = "DB_FILE" in f.read()
    # versions before v3.0 keep data in JSON files: write today's data out for them first
    exported = [] if uses_db else export_to_files()
    try:
        installed = install_files(folder, f"rollback to {meta.get('commit', '')[:7] or 'older version'}")
    except Exception:
        for k in exported:
            try:
                os.remove(os.path.join(DATA, *k.split("/")))
            except OSError:
                pass
        raise
    if exported and installed:
        retire_db()
        log("Rolled back to a version without the database. Your data was written out as JSON files for it; "
            "binder.db was renamed, not deleted.")
    if installed or same_file(os.path.join(folder, "server.py"), os.path.join(APP, "server.py")):
        write_json(VERSION_FILE, {"version": meta.get("version", ""), "commit": meta.get("commit", ""), "subject": meta.get("subject", ""),
                                  "date": meta.get("date", ""), "installed": now_iso(), "paused": True})
        shutil.rmtree(folder, ignore_errors=True)   # it's the running version now
    return installed


# Updates are never installed by themselves (not on start, not on a schedule).
# The only way in is Settings -> About -> Check for updates, which shows the changes and asks first.


def restart_self(delay=0):
    if delay:
        time.sleep(delay)
    log("Restarting with the new server.py...")
    try:
        os.execv(sys.executable, [sys.executable, "-u", os.path.abspath(__file__)])
    except OSError as e:   # very unlikely; don't leave updates blocked until the container restarts
        log(f"Couldn't restart ({e}). Restart the container to finish the update.")
        with job_lock:
            big["what"] = ""


def version_info():
    out = {}
    for name in APP_FILES:
        try:
            out[name] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(os.path.join(APP, name))))
        except OSError:
            out[name] = ""
    cur = current_version()
    size = sum(os.path.getsize(DB_FILE + ext) for ext in ("", "-wal") if os.path.exists(DB_FILE + ext))
    out["storage"] = {"kind": "database", "file": "data/binder.db", "size": size}
    out.update(version=file_version(os.path.join(APP, "server.py")),
               updatesFolder=os.path.isdir(UPDATES), github=bool(GH_REPO), repo=GH_REPO,
               commit=cur.get("commit", ""), subject=cur.get("subject", ""), date=cur.get("date", ""),
               installed=cur.get("installed", ""), paused=bool(cur.get("paused")),
               previous=list_versions(), **{k: update_status[k] for k in ("source", "checked", "error")})
    return out
