"""Type check for the page code (app/*.js), with TypeScript's checker. Runs on this PC only, never on the server.

    python3 tests/type_check.py          list notes that aren't in tests/type_baseline.txt
    python3 tests/type_check.py --save   accept today's notes as the starting point

Needs Node (nodejs.org); without it the check is skipped. The code stays plain JavaScript: the checker only reads it.
Notes already in the baseline are known and harmless (like subtracting two dates); a new note is worth a look,
especially "Cannot find name" (a misspelled or missing function).
"""
import os, re, shutil, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(REPO, "tests", "type_baseline.txt")
TS = "typescript@5.6.3"


def npx():
    found = shutil.which("npx") or shutil.which("npx.cmd")
    if found:
        return found
    default = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "nodejs", "npx.cmd")
    return default if os.path.isfile(default) else None


def main():
    tool = npx()
    if not tool:
        print("SKIP  type check (Node isn't installed)")
        return
    env = dict(os.environ, PATH=os.path.dirname(tool) + os.pathsep + os.environ.get("PATH", ""))
    out = subprocess.run([tool, "-y", "-p", TS, "tsc", "-p", "jsconfig.json"], cwd=REPO, capture_output=True,
                         text=True, encoding="utf-8", errors="replace", env=env, shell=os.name == "nt").stdout
    # line numbers change with every edit, so notes are compared by file, kind and message
    notes = sorted(re.sub(r"\(\d+,\d+\)", "", l).strip() for l in out.splitlines() if "error TS" in l)
    if "--save" in sys.argv:
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(notes) + "\n")
        print(f"Saved {len(notes)} known notes to tests/type_baseline.txt")
        return
    known = open(BASELINE, encoding="utf-8").read().splitlines() if os.path.exists(BASELINE) else []
    left = list(known)
    new = []
    for n in notes:
        if n in left:
            left.remove(n)
        else:
            new.append(n)
    for n in new:
        print("NEW   " + n)
    for l in out.splitlines():
        if new and any(re.sub(r"\(\d+,\d+\)", "", l).strip() == n for n in new):
            print("      at " + l.split(":")[0])
    print(f"Type check: {len(new)} new note(s)." if new else f"Type check: nothing new ({len(notes)} known notes).")
    sys.exit(1 if new else 0)


if __name__ == "__main__":
    main()
