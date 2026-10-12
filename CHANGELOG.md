# Changelog

Versions go up by 0.1 for each app update (new features or fixes) and by a whole number for big changes, like a redesign or a change to how data is stored. Changes that don't touch the app, like README edits, don't get a new number.

The binder shows these in **Settings → About → Check for updates**.

## v2.6 (October 11, 2026)

- **Card shows:** new calendar button at the top. Lists upcoming card shows in your towns from TreasureHunter.show, by month, with the date, venue and a link to each show. Pokémon/TCG shows are tagged, with a Pokémon / TCG or All filter. Shows found since your last scan are marked New.
- Checks once a week by itself (turn off in the panel), or tap **Scan now** any time.
- Towns are editable in the panel. Default: Richmond, Midlothian, Chesterfield, Chester, Glen Allen, Henrico, Short Pump, Mechanicsville, Ashland, Petersburg, Colonial Heights, Hopewell, Powhatan and Sandston.
- Your towns are included in backups. Past shows drop off by themselves.

## v2.5 (October 11, 2026)

- **Card list gap warning.** When a binder's card list might be incomplete, an asterisk (*) shows on the card count at the top, with a short note under the binder name:
  - Set binders: when the card database is missing card numbers between 1 and the set's printed total, it lists which ones.
  - Master set binders: always, since the card database doesn't have every promo, trainer kit or McDonald's card.

## v2.4 (October 11, 2026)

- **No more automatic updates.** Restarting the container no longer installs anything. Updates only come from Settings → About → Check for updates, which shows the changes and asks you to confirm first.
- Roll back no longer mentions paused updates, since nothing updates by itself now

## v2.3 (October 11, 2026)

- Master set binders: the eBay sold, TCGplayer and PriceCharting links on a card now search that card's own set and printed number (like "Expedition Totodile 134/165"), instead of the binder name and an internal card id.

## v2.2 (October 11, 2026)

- **Pokémon master set binders:** Menu → + Add a set or Pokémon → A Pokémon. Search by name or Pokédex number (like Totodile or 158) to make a binder of every English card of that Pokémon, from every set, oldest first.
- Looks and works like a set binder (prices, shopping list, upgrades, stats, photos, backup). Each card shows which set it's from, and the set filter replaces the rarity filter.
- The Pokémon's game sprite shows next to the binder name and in the sets menu (Crystal sprites for #1 to #251, Black/White for #252 to #649, see-through backgrounds). Sprites come from PokeAPI and are saved on your server.
- The Pokémon list is made once from every set (about 2 minutes, in the background) and refreshed about once a month so new cards join your master set binders.
- One copy of each card (Unlimited), same as set binders. Some promos and trainer kit cards aren't in the card database yet, so they won't show up.

## v2.1 (October 11, 2026)

- Purchase log fits phone screens: each purchase shows the card and price on top, with date, set, place and seller underneath (no sideways scrolling)
- Shopping list order buttons stay on one line on phones

## v2.0 (October 11, 2026)

- **Backup and restore** in Settings → Backup. Download one file with every binder's cards, purchases, sellers, notes, photos, prices and settings. Restoring asks first and saves a safety copy of your current data on your server (in `backups/`, last 5 kept).
- **Upgrades** view: cards you own in worn conditions (HP and DMG by default, MP optional), what a better copy costs, and the cost after selling yours. Choices are saved per binder.
- **All binders** summary at the top of the sets menu: cards owned, collection value vs. paid, cost to finish, and full sets value across every binder. Each set row also shows its value. Blurred in privacy mode.

## v1.9 (October 11, 2026)

- **Shopping list order:** Cheapest, Priciest, Set number, or My order. Drag the ⠿ handle (or focus it and use the arrow keys) to move a card, and the running total and budget update as you go.
- Your order is saved on your server per set, so it's the same on your phone and computer. Newly needed cards join the end, cheapest first.
- Shopping list fits on phone screens without sideways scrolling (card pictures hide on small screens)

## v1.8 (October 11, 2026)

- Number search keeps working while you type the slash (`1/` shows card 1 before you finish `1/105`)

## v1.7 (October 11, 2026)

- Searching a number (like `2`) now finds only that card number, not names with that digit in them (like Dark Porygon2)

## v1.6 (October 11, 2026)

- **Custom tab icon:** Settings → Tab icon → Choose image. Your image is saved on your server only, never in this repository. "Use default" switches back.
- New default tab icon (a little binder page) instead of the browser's globe

## v1.5 (October 11, 2026)

- Prices now ask TCGplayer for each condition separately (NM, LP, MP, HP, Damaged), so every condition gets up to its 5 newest sales. TCGplayer only returns 5 sales per request, which left NM and HP empty on many cards.
- Same number of requests per card as before, so refreshes take about as long

## v1.4 (October 11, 2026)

- Fixed TCGplayer product lookups failing for cards the binder hasn't seen before (affects newly added sets)
- The price test (`--test`) shows more detail when a lookup fails

## v1.3 (October 11, 2026)

- **Each binder has its own price options.** Neo Destiny can use LP while Neo Genesis uses NM. Binders keep whatever you had set before until you change them.
- **A warning before changing the price average** explains what will change: totals, the history chart, and when graded prices fill in
- **Search by card number**, like `1/105`, `#1`, or `001`
- **Recent sales tab** on each card: the newest 5 sales for NM, LP, MP, HP, and Damaged (plus your graded price, if you picked one), so you can compare conditions. Fills in after the next refresh.

## v1.2 (October 11, 2026)

- **Choose your two prices** in Settings → Price average. Each one can be a raw condition (NM, LP, MP, HP, Damaged) or a graded price (PSA, BGS, CGC, SGC, TAG, ACE, or any company, grade 10 down to 1). The second can be turned off.
- Graded prices come from eBay sold listings on PriceCharting, sorted by the company and grade in each title. 1st Edition, Shadowless, Japanese, and lots are skipped.
- The card details boxes follow your choices, like "PSA 9 average" and "LP average"
- Set totals use the combined average when both prices are raw conditions, or the first price when a graded one is picked (falling back to the second if there are no sales)
- The PriceCharting button opens the card's own page once it's been found

## v1.1 (October 11, 2026)

- Privacy mode blurs cards owned and % complete again, along with the money totals

## v1.0 (October 11, 2026)

First numbered version.

- **Check for updates** shows what's new and asks before installing
- **Roll back** to one of the last 3 versions from Settings → About; automatic updates pause until you install an update yourself
- Privacy mode no longer shifts the page when turned on

Already included from earlier, unnumbered versions:

- Multiple sets, card images (owned in color, needed in greyscale), Unlimited only
- TCGplayer prices: separate LP and MP averages plus every condition, daily automatic refresh and a manual refresh button
- Price history, biggest movers, shopping list with a budget
- Purchase log with date, price, place, and seller handle; copies owned always match purchases
- Front and back photos of your copies
- Privacy mode, five dark themes, phone layout
- Self-updates from this GitHub repository, no key needed
