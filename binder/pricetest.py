"""Price test for one card: python server.py --test neo4-1.

Part of the server: server.py runs the files in binder/ in order, as if they were written in it,
so they all share one set of names."""

def test_card(card_id):
    try:
        print(f"Card {card_id}: looking up the TCGplayer product (fresh, not the saved one)")
        pid = product_id(card_id, {}, verbose=True)
        print(f"Card {card_id}: TCGplayer product id = {pid}")
        if pid:
            test_tcgplayer(pid)
    except Exception as e:
        print(f"Card {card_id}: couldn't reach TCGplayer: {e}")
    sid, _, n = card_id.rpartition("-")
    card = next((c for c in set_cards(sid) if c["n"] == n), None)
    if not card:
        return
    print("Market prices (TCGdex):")
    try:
        tc = tcgdex_card(sid, card, {})
        usd = eur_to_usd()
        print(f"  Euro to dollar rate: {usd or 'not available, Cardmarket left out'}")
        mkt = tcgdex_market(tc, card.get("rarity", ""), usd) if tc else {}
        print(f"  Card: {tc.get('id') if tc else 'not found'}")
        if tc and not mkt:
            print("  No prices on this card")
        if mkt.get("tp"):
            print(f"  TCGplayer market ${mkt['tp']} ({mkt.get('tpVar')}), low ${mkt.get('tpLow')}, updated {mkt.get('tpUpd')}")
        if mkt.get("cm30") or mkt.get("cmTrend"):
            print(f"  Cardmarket 30-day avg ${mkt.get('cm30')}, trend ${mkt.get('cmTrend')} (converted from euros), updated {mkt.get('cmUpd')}")
    except Exception as e:
        print(f"  Couldn't reach TCGdex: {e}")
    print("Graded (PriceCharting sold listings, Unlimited only):")
    try:
        groups, url, _ = graded_for(sid, card, {})
    except Exception as e:
        print(f"  Couldn't reach PriceCharting: {e}")
        return
    print(f"  Page: {url or 'not found'}")
    if url and not groups:
        print("  No graded sales found on the page")
    for key in sorted((groups or {}), key=lambda k: (k.startswith("Any"), k)):
        a2, c2, d2 = groups[key]
        print(f"  {key:<8} ${a2}  from {c2} sale{'s' if c2 != 1 else ''}, latest {d2}")


def test_tcgplayer(pid):
    print("Sales by condition:")
    sales = condition_sales(pid, verbose=True)
    print(f"Sales collected: {len(sales)}")
    for s in [x for x in sales if is_match(x)][:10]:
        print(f"  {s.get('orderDate', '')[:10]}  {s.get('condition')}  {s.get('variant')}  ${s.get('purchasePrice')}")
    avg, count, last = lp_mp_average(sales)
    print(f"LP/MP Unlimited average: {avg} from {count} sales (latest {last})")
    print("By condition (Unlimited, TCGplayer):")
    for short, (a, c, d) in sorted(by_condition(sales).items(), key=lambda kv: list(COND_SHORT.values()).index(kv[0])):
        print(f"  {short:<4} ${a}  from {c} sale{'s' if c != 1 else ''}, latest {d}")
