"""Cleanup check for Pokemon Binder: run it after every middle-number release (v3.19, v3.20, ...).

    python3 tests/cleanup_check.py

Lists leftover code that nothing uses any more and names that are used twice (the later one silently
replaces the earlier one, which is how Settings > About > Status broke in v3.19). It changes nothing:
review each item, remove what's really unused, then run tests/smoke_test.py and compare screenshots.
Exits with 1 if anything is listed. Python standard library only.
"""
import ast, collections, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEEP = {"UPDATE_FILES",    # read by older versions' updaters, so rolling back keeps working
        "settingsPages"}   # used once on purpose: creating it sets up the Settings sections
found = []


def report(title, items):
    items = sorted(set(items))
    print(("OK    " if not items else "CHECK ") + title + ("" if not items else ": " + ", ".join(items)))
    found.extend(items)


def once(name, text):
    """True if a code name (function or value) appears only where it's defined."""
    return len(re.findall(r"\b" + re.escape(name) + r"\b", text)) == 1


def main():
    src = open(os.path.join(REPO, "server.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    defs = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    report("server: names defined twice", [n for n, c in collections.Counter(defs).items() if c > 1])
    report("server: functions nothing uses", [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and once(n.name, src)])
    names = [t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)]
    report("server: settings/values nothing uses", [n for n in names if n not in KEEP and once(n, src)])

    page = open(os.path.join(REPO, "index.html"), encoding="utf-8").read()
    st, en = page.index("<style>"), page.index("</style>")
    css, rest = page[st:en], page[:st] + page[en:]
    script = page[page.index("<script>", en):]
    fns = re.findall(r"^\s*(?:async\s+)?function\s+(\w+)\s*\(", script, re.M)
    report("page: functions defined twice", [f for f, c in collections.Counter(fns).items() if c > 1])
    report("page: functions nothing uses", [f for f in fns if once(f, script)])
    tops = re.findall(r"^(?:const|let|var)\s+(\w+)", script, re.M)
    report("page: values nothing uses", [t for t in tops if t not in KEEP and once(t, script)])
    ids = re.findall(r'\sid="([^"]+)"', page[:page.index("<script>", en)])
    report("page: ids used twice", [i for i, c in collections.Counter(ids).items() if c > 1])
    classes = set(re.findall(r"\.([a-zA-Z][\w-]*)", re.sub(r"url\([^)]*\)|\d+\.\d+", "", css)))
    built = tuple(re.findall(r'"([a-z][\w]*-)"\s*\+', rest))   # names built from pieces, like "cv-"+key
    report("page: styles for classes nothing uses", [c for c in classes if not c.startswith(built)
                                                      and not re.search(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])", rest)])

    print()
    print("Nothing to clean up." if not found else f"{len(found)} item(s) to look at. Some may be built from pieces "
          "(like \"has-\"+name), so search before removing.")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
