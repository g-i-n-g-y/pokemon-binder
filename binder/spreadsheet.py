"""Totals per binder, spreadsheet import and export.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

# ---------- totals per set (for the all-binders summary) ----------

def set_totals(sid):
    """Same math as the page header: value counts owned copies at their condition's price when set."""
    coll = read_json(sdir(sid, "collection.json"), {})
    cards = (card_list(sid) or []) + extra_list(sid) + custom_list(sid)
    prices = read_json(sdir(sid, "prices.json"), {})
    p, info = prices.get("p") or {}, prices.get("info") or {}
    t = {"owned": 0, "count": len(cards), "value": 0.0, "paid": 0.0, "need": 0.0, "full": 0.0}
    for c in cards:
        n = c["n"]
        base = (p.get(n) or [0])[0] or 0
        rec = coll.get(n) if isinstance(coll.get(n), dict) else {}
        t["full"] += base
        t["paid"] += sum(b.get("price") for b in rec.get("purchases") or []
                         if isinstance(b, dict) and isinstance(b.get("price"), (int, float)))
        q = rec.get("qty") or 0
        if q > 0:
            t["owned"] += 1
            cp = ((info.get(n) or {}).get("cond") or {}).get(rec.get("cond")) if rec.get("cond") else None
            t["value"] += ((cp[0] if cp else 0) or base) * q
        else:
            t["need"] += base
    return {k: round(v, 2) if isinstance(v, float) else v for k, v in t.items()}


# ---------- spreadsheet import (Excel .xlsx or .csv) ----------
# Reads a card list like the Neo Destiny tracker spreadsheet: a header row with a card number column
# ("Set #", "No.", "Number") and any of Qty / Status, Condition, Your Cost, Notes. Only adds: cards the
# file lists as owned are marked owned; nothing is marked needed and nothing already logged is removed.

MAX_IMPORT = 10 * 1024 * 1024
XNS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
HEADERS = {
    "num": ("set#", "setno", "setnumber", "number", "no", "#", "cardnumber", "cardno", "num", "card#"),
    "name": ("cardname", "name", "card", "pokemon"),
    "qty": ("qty", "quantity", "copies", "count", "owned#", "have"),
    "status": ("status", "owned", "own"),
    "cond": ("condition", "cond"),
    "cost": ("yourcost", "cost", "paid", "pricepaid", "purchaseprice", "buyprice", "costeach"),
    "note": ("notes", "note", "comments", "comment"),
}


def _hkey(t):
    return re.sub(r"[^a-z0-9#]", "", str(t or "").lower())


def _xml(z, name, limit=30 * 1024 * 1024):
    import xml.etree.ElementTree as ET
    if z.getinfo(name).file_size > limit:
        raise ValueError("That spreadsheet is too big")
    data = z.read(name)
    if b"<!DOCTYPE" in data[:2000].upper() or b"<!ENTITY" in data[:2000].upper():
        raise ValueError("That spreadsheet can't be read")
    return ET.fromstring(data)


def _col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(raw):
    """Every sheet in an .xlsx as {sheet name: [[cell, ...], ...]}, using Python's built-in zip and XML tools."""
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise ValueError("That file isn't an Excel spreadsheet or CSV")
    with z:
        names = set(z.namelist())
        if "xl/workbook.xml" not in names:
            raise ValueError("That file isn't an Excel spreadsheet or CSV")
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in _xml(z, "xl/sharedStrings.xml").iter(XNS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(XNS + "t")))
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for r in _xml(z, "xl/_rels/workbook.xml.rels"):
                rels[r.get("Id")] = r.get("Target", "")
        out = {}
        for sh in _xml(z, "xl/workbook.xml").iter(XNS + "sheet"):
            target = rels.get(sh.get(RNS + "id"), "")
            path = target.lstrip("/") if target.startswith("/") else "xl/" + target
            if path not in names:
                continue
            rows = []
            for row in _xml(z, path).iter(XNS + "row"):
                cells = {}
                for c in row.iter(XNS + "c"):
                    t, v = c.get("t"), c.find(XNS + "v")
                    if t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(XNS + "t"))
                    elif v is None or v.text is None:
                        val = None   # a formula Excel hasn't saved a result for
                    elif t == "s":
                        val = shared[int(v.text)] if v.text.isdigit() and int(v.text) < len(shared) else ""
                    elif t in ("str", "e"):
                        val = v.text
                    elif t == "b":
                        val = v.text == "1"
                    else:
                        try:
                            val = float(v.text)
                        except ValueError:
                            val = v.text
                    if c.get("r"):
                        cells[_col(c.get("r"))] = val
                if cells:
                    rows.append([cells.get(i) for i in range(max(cells) + 1)])
                if len(rows) > 5000:
                    break
            out[sh.get("name", "")] = rows
        return out


def read_sheet(raw):
    """The card rows of a spreadsheet: [{"row": line number, "num", "name", "qty", "status", "cond", "cost", "note"}]."""
    import csv
    if raw[:2] == b"PK":
        sheets = read_xlsx(raw)
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        sheets = {"csv": list(csv.reader(io.StringIO(text)))}
    for rows in sheets.values():
        for hi, header in enumerate(rows[:10]):
            keys = [_hkey(h) for h in header]
            cols = {}
            for field, names in HEADERS.items():
                for i, k in enumerate(keys):
                    if k in names and i not in cols.values():
                        cols[field] = i
                        break
            if "num" not in cols or not ({"qty", "status"} & set(cols)):
                continue
            out = []
            for li, r in enumerate(rows[hi + 1:], start=hi + 2):
                get = lambda f: r[cols[f]] if f in cols and cols[f] < len(r) else None
                if get("num") in (None, ""):
                    continue
                out.append({"row": li, **{f: get(f) for f in HEADERS}})
            return out
    raise ValueError("Couldn't find the card list. The file needs a header row with a card number column "
                     "(like \"Set #\") and a Qty or Status column.")


def _clean_num(v):
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    t = str(v).strip().lstrip("#").split("/")[0].strip()
    if CUSTOM_N.fullmatch(t.lower()):
        return t.lower()
    return t.lstrip("0") or t if t.isdigit() else t


def _simple(t):
    t = str(t or "").lower().replace("é", "e").replace("♀", "f").replace("♂", "m")
    return re.sub(r"[^a-z0-9]", "", t)


def same_name(a, b):
    """Card names match, allowing small spelling differences (like Imposter / Impostor)."""
    import difflib
    a, b = _simple(a), _simple(b)
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def _money(v):
    if v in (None, ""):
        return None
    try:
        f = float(str(v).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None
    return round(f, 2) if f > 0 else None


def import_plan(sid, rows):
    """What importing these rows would change, without changing anything."""
    if is_dex(sid):
        raise ValueError("Spreadsheet import works for set binders, not Pokémon master sets")
    cards = {c["n"]: c for c in set_cards(sid)}
    coll = read_json(sdir(sid, "collection.json"), {})
    changes, skipped, already, need = [], [], 0, 0
    seen = set()
    for r in rows:
        n = _clean_num(r["num"])
        card = cards.get(n)
        if not card:
            skipped.append({"row": r["row"], "why": f"No card number {r['num']} in this set"})
            continue
        if r.get("name") and not same_name(r["name"], card["name"]):
            skipped.append({"row": r["row"], "why": f"#{n} is {card['name']} here, but the file says {r['name']}"})
            continue
        if n in seen:
            skipped.append({"row": r["row"], "why": f"#{n} is listed twice; the first row was used"})
            continue
        seen.add(n)
        qty = None
        if r.get("qty") not in (None, ""):
            try:
                qty = max(0, int(float(str(r["qty"]).strip())))
            except ValueError:
                skipped.append({"row": r["row"], "why": f"Qty \"{r['qty']}\" isn't a number"})
                continue
        elif str(r.get("status") or "").strip().lower() in ("owned", "own", "yes", "y", "true", "x", "1"):
            qty = 1
        if not qty:
            need += 1
            continue
        rec = coll.get(n) or {}
        have = int(rec.get("qty") or 0)
        cond = str(r.get("cond") or "").strip().upper()
        cond = cond if cond in RAW_CONDS else ""
        cost = _money(r.get("cost"))
        note = str(r.get("note") or "").strip()[:500]
        add = max(0, qty - have)
        ch = {"n": n, "name": card["name"], "qty": qty, "have": have, "add": add}
        if cond and not rec.get("cond"):
            ch["cond"] = cond
        if note and not rec.get("note"):
            ch["note"] = note
        if cost and add and have == 0:
            ch["each"] = round(cost / qty, 2)   # "Your Cost" is what you paid for all your copies
        if add or "cond" in ch or "note" in ch:
            changes.append(ch)
        else:
            already += 1
    return {"changes": changes, "skipped": skipped[:50], "skippedCount": len(skipped),
            "already": already, "need": need, "rows": len(rows)}


def import_template(sid):
    """A CSV of every card in the binder with what's already saved, ready to fill in and import."""
    import csv
    coll = read_json(sdir(sid, "collection.json"), {})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Set #", "Card Name", "Rarity", "Qty", "Condition", "Your Cost", "Notes"])
    for c in set_cards(sid):
        rec = coll.get(c["n"]) or {}
        paid = sum(b.get("price") or 0 for b in rec.get("purchases") or [] if isinstance(b, dict))
        w.writerow([c["n"], c["name"], c.get("rarity", ""), int(rec.get("qty") or 0), rec.get("cond") or "",
                    f"{paid:.2f}" if paid else "", rec.get("note") or ""])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")   # the mark helps Excel read accents like Pokémon


def _xlsx(sheets):
    """A small Excel file (standard library only): sheets = [(name, header, rows)], first row bold and frozen."""
    from xml.sax.saxutils import escape
    def col(i):
        s = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s
    def cell(ref, v, style=0):
        st = f' s="{style}"' if style else ""
        if isinstance(v, bool) or v is None or v == "":
            return f'<c r="{ref}"{st}/>' if style else ""
        if isinstance(v, (int, float)):
            return f'<c r="{ref}"{st}><v>{v}</v></c>'
        return f'<c r="{ref}"{st} t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'
    files, used = {}, set()
    names = []
    for k, (name, header, rows, money) in enumerate(sheets, 1):
        nm = re.sub(r"[\\/?*\[\]:]", "", name)[:31] or f"Sheet{k}"
        base, n = nm, 2
        while nm.lower() in used:
            nm = (base[:28] + f" {n}"); n += 1
        used.add(nm.lower()); names.append(nm)
        widths = [max(len(str(h)), *(len(str(r[i])) for r in rows[:500]) if rows else [0]) for i, h in enumerate(header)]
        cols = "".join(f'<col min="{i+1}" max="{i+1}" width="{min(48, max(8, w + 2))}" customWidth="1"/>' for i, w in enumerate(widths))
        body = ['<row r="1">' + "".join(cell(f"{col(i)}1", h, 1) for i, h in enumerate(header)) + "</row>"]
        for j, r in enumerate(rows, 2):
            body.append(f'<row r="{j}">' + "".join(cell(f"{col(i)}{j}", v, 2 if i in money and isinstance(v, (int, float)) else 0) for i, v in enumerate(r)) + "</row>")
        files[f"xl/worksheets/sheet{k}.xml"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            f'<cols>{cols}</cols><sheetData>{"".join(body)}</sheetData></worksheet>')
    n = len(names)
    files["[Content_Types].xml"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + "".join(f'<Override PartName="/xl/worksheets/sheet{k}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for k in range(1, n + 1))
        + "</Types>")
    files["_rels/.rels"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    files["xl/workbook.xml"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + "".join(f'<sheet name="{escape(nm, {chr(34): "&quot;"})}" sheetId="{k}" r:id="rId{k}"/>' for k, nm in enumerate(names, 1)) + "</sheets></workbook>")
    files["xl/_rels/workbook.xml.rels"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(f'<Relationship Id="rId{k}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{k}.xml"/>' for k in range(1, n + 1))
        + f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    files["xl/styles.xml"] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00"/></numFmts>'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels", "xl/styles.xml"):
            z.writestr(name, files[name])
        for k in range(1, n + 1):
            z.writestr(f"xl/worksheets/sheet{k}.xml", files[f"xl/worksheets/sheet{k}.xml"])
    return out.getvalue()


def export_collection(only=None):
    """Every binder (or just the ones in `only`) in one Excel file: an "All binders" sheet plus one sheet per binder."""
    sl = sets_list()
    header = ["Binder", "Set", "Number", "Card", "Rarity", "Status", "Copies", "Condition", "Paid", "Price each", "Value",
              "7-day change %", "30-day change %", "90-day change %", "Last sale", "First owned", "Notes"]
    money = {8, 9, 10}
    every, per = [], []
    for sid in sl["order"]:
        if only and sid not in only:
            continue
        meta = sl["meta"].get(sid, {})
        bname = meta.get("name", sid)
        coll = read_json(sdir(sid, "collection.json"), {})
        pr = read_json(sdir(sid, "prices.json"), {}) or {}
        prices, info = pr.get("p") or {}, pr.get("info") or {}
        trends = set_trends(sid, today_local())["cards"]   # price changes, for spotting cards that are climbing
        rows = []
        cards = card_list(sid)
        cards = (cards or []) + extra_list(sid) + custom_cards(sid)
        for c in cards:
            rec = coll.get(c["n"]) or {}
            qty = int(rec.get("qty") or 0) if isinstance(rec.get("qty"), (int, float)) else 0
            paid = round(sum(b.get("price") or 0 for b in rec.get("purchases") or [] if isinstance(b, dict) and isinstance(b.get("price"), (int, float))), 2)
            each = (prices.get(c["n"]) or [0])[0] or 0
            first = (rec.get("got") or "")[:10] or min((b.get("d") or "" for b in rec.get("purchases") or [] if isinstance(b, dict) and b.get("d")), default="")
            t = trends.get(c["n"]) or {}
            def change(days, t=t):
                was, now = (t.get("at") or {}).get(str(days)), t.get("last")
                return round((now[1] - was[1]) / was[1] * 100, 1) if was and now and was[1] else ""
            last_sale = str((info.get(c["n"]) or {}).get("last") or "")[:10]
            setname = c.get("set") or (bname if not (is_multi(sid) or c.get("extra")) else "")
            num = c.get("num") or c["n"]
            rows.append([bname, setname, num, c.get("name", ""), c.get("rarity", ""), "Owned" if qty > 0 else "Need", qty,
                         rec.get("cond") or "", paid or "", round(each, 2) if each else "", round(each * qty, 2) if each and qty else "",
                         change(7), change(30), change(90), last_sale, first if qty > 0 else "", rec.get("note") or ""])
        every += rows
        per.append((bname, header, rows, money))
    if len(per) == 1:   # one binder: just its own sheet
        return _xlsx(per)
    return _xlsx([("All binders", header, every, money)] + per)


def apply_import(sid, plan):
    """Make the changes from import_plan. Saves a backup first. Returns the backup's file name."""
    if not plan["changes"]:
        return ""
    name = auto_backup("before-import")
    with lock:
        coll = read_json(sdir(sid, "collection.json"), {})
        for ch in plan["changes"]:
            rec = coll.get(ch["n"]) or {}
            buys = [b for b in (rec.get("purchases") or []) if isinstance(b, dict)]
            for _ in range(ch["add"]):
                buys.append({"d": "", "price": ch.get("each"), "where": ""})
            rec["purchases"] = buys
            rec["qty"] = len(buys)
            if ch.get("cond"):
                rec["cond"] = ch["cond"]
            if ch.get("note"):
                rec["note"] = ch["note"]
            coll[ch["n"]] = rec
        write_json(sdir(sid, "collection.json"), coll)
    log(f"{sid}: imported a spreadsheet ({len(plan['changes'])} cards changed)")
    return name


# ---------- download for TCGplayer (Collection → Import) ----------
# TCGplayer's import reads one card per line: quantity, its name, its set code in brackets and its number, like
# "1 Dark Gengar [N4] 006/105". Its Share adds the printing and condition after that, but its Import turns those
# lines down, so they're left off and the list is sorted by condition instead, to make fixing them in TCGplayer quick. Its set codes and names differ from the card database's, so they come from
# TCGCSV, a free daily copy of TCGplayer's catalog, matched by the TCGplayer product id each price check saves.
TCGCSV = "https://tcgcsv.com/tcgplayer/3"   # 3 = Pokémon
TCG_CATALOG = os.path.join(DATA, "tcg_catalog")


def tcg_groups():
    """TCGplayer's Pokémon sets: {group id: [set code, release date]}. Saved for a week."""
    path = os.path.join(TCG_CATALOG, "groups.json")
    saved = read_json(path, None)
    if saved and time.time() - saved.get("at", 0) < 7 * DAY:
        return saved["groups"]
    try:
        raw = json.loads(http_get(f"{TCGCSV}/groups", timeout=30)).get("results") or []
    except Exception:
        if saved:
            return saved["groups"]
        raise
    groups = {str(g["groupId"]): [g.get("abbreviation") or "", str(g.get("publishedOn") or "")[:10]]
              for g in raw if isinstance(g, dict) and g.get("groupId")}
    os.makedirs(TCG_CATALOG, exist_ok=True)
    write_json(path, {"at": time.time(), "groups": groups})
    return groups


def tcg_products(gid):
    """One TCGplayer set's cards: {product id: [name, number, [printings]]}, printings like "Unlimited Holofoil".
    Saved for a month."""
    path = os.path.join(TCG_CATALOG, f"{gid}.json")
    saved = read_json(path, None)
    if saved and saved.get("v") == 2 and time.time() - saved.get("at", 0) < 30 * DAY:
        return saved["p"]
    try:
        raw = json.loads(http_get(f"{TCGCSV}/{gid}/products", timeout=30)).get("results") or []
        kinds = {}   # the printings each card comes in, from TCGplayer's price list
        for x in json.loads(http_get(f"{TCGCSV}/{gid}/prices", timeout=30)).get("results") or []:
            if x.get("subTypeName"):
                kinds.setdefault(str(x.get("productId")), []).append(x["subTypeName"])
    except Exception:
        if saved and saved.get("v") == 2:
            return saved["p"]
        raise
    prods = {}
    for p in raw:
        num = next((e.get("value") for e in p.get("extendedData") or [] if e.get("name") == "Number"), "")
        if num:   # cards have a number; sealed products don't
            prods[str(p["productId"])] = [p.get("name") or "", num, kinds.get(str(p["productId"]), [])]
    os.makedirs(TCG_CATALOG, exist_ok=True)
    write_json(path, {"v": 2, "at": time.time(), "p": prods})
    return prods


def _tcg_line(groups, pid, name, num, date):
    """(set code, TCGplayer name, number, printings) for one card, or None. Looks in the TCGplayer sets released closest to it."""
    def apart(gday):
        try:
            return abs((datetime.fromisoformat(gday) - datetime.fromisoformat((date or "").replace("/", "-")[:10])).days)
        except ValueError:
            return 99999
    near = sorted(groups, key=lambda g: apart(groups[g][1]))
    lead = re.match(r"0*(\d+)", str(num or ""))
    for gid in near[:8]:
        prods = tcg_products(gid)
        if pid and str(pid) in prods:
            name_, num_, kinds = prods[str(pid)]
            return groups[gid][0], name_, num_, tuple(kinds)
        if not pid and lead:   # no TCGplayer id yet: the same name and number in a set from that time
            for pname, pnum, kinds in prods.values():
                m = re.match(r"0*(\d+)", pnum)
                if m and m.group(1) == lead.group(1) and _simple(pname) == _simple(name):
                    return groups[gid][0], pname, pnum, tuple(kinds)
    return None


TCG_CONDS = {"NM": "Near Mint", "LP": "Lightly Played", "MP": "Moderately Played", "HP": "Heavily Played", "DMG": "Damaged"}


def tcg_printing(kinds, rarity, rev):
    """Which of TCGplayer's printings a copy is. The binder collects Unlimited, so 1st Edition is left out;
    Reverse Holofoil only for copies marked reverse holo. Cards that come both plain and holo go by rarity."""
    if rev and "Reverse Holofoil" in kinds:
        return "Reverse Holofoil"
    left = [k for k in kinds if not k.startswith("1st Edition") and k != "Reverse Holofoil"]
    if len(left) > 1:
        holo = "holo" in (rarity or "").lower()
        left = [k for k in left if ("Holofoil" in k) == holo] or left
    return left[0] if left else ""


def export_tcgplayer(only=None):
    """(text, cards left out) for TCGplayer's Collection import: every owned card in the binders asked for."""
    sl = sets_list()
    groups = tcg_groups()
    lines, missed = {}, []
    for sid in sl["order"]:
        if only and sid not in only:
            continue
        coll = read_json(sdir(sid, "collection.json"), {})
        ids = read_json(sdir(sid, "tcg_ids.json"), {})
        set_day = sl["meta"].get(sid, {}).get("releaseDate", "")
        for c in (card_list(sid) or []) + extra_list(sid) + custom_cards(sid):
            rec = coll.get(c["n"]) or {}
            qty = int(rec.get("qty") or 0) if isinstance(rec.get("qty"), (int, float)) else 0
            if qty <= 0:
                continue
            ref, _, num = card_ref(sid, c)
            found = None if c.get("custom") and not ids.get(c["n"]) else \
                _tcg_line(groups, ids.get(ref or c["n"]), c.get("name", ""), num, c.get("date") or set_day)
            if not found:
                missed.append(c.get("name", c["n"]))
                continue
            code, name, number, kinds = found
            rev = min(qty, sum(1 for b in rec.get("purchases") or [] if isinstance(b, dict) and b.get("rev")))
            cond = TCG_CONDS.get(rec.get("cond") or "", "Lightly Played")   # for sorting; no condition set counts as LP
            for n_, is_rev in ((qty - rev, False), (rev, True)):   # reverse holo copies get a line of their own
                if n_ > 0:
                    key = (code, name, number, tcg_printing(kinds, c.get("rarity", ""), is_rev), cond)
                    lines[key] = lines.get(key, 0) + n_   # the same card in two binders is one line
    order = list(TCG_CONDS.values())   # Near Mint first, then Lightly Played, and so on
    rows = sorted(lines.items(), key=lambda kv: (order.index(kv[0][4]), kv[0][3] == "Reverse Holofoil"))
    text = "".join(f"{q} {name} [{code}] {num}\n" for (code, name, num, printing, cond), q in rows)
    return text, missed
