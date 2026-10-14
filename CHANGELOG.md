# Changelog

Version numbers, starting after v2.11:

- **Whole number** (3.0): big changes, like a redesign or a change to how data is stored
- **Middle number** (2.12): new features or bigger changes you'll notice
- **Last number** (2.11.1): small fixes and touch-ups, like spacing or a scroll bar

Versions up to v2.11 went up by 0.1 for every update, including small fixes, and keep their numbers. Changes that don't touch the app, like README edits, don't get a new number.

The binder shows these in **Settings → About → Check for updates**.

## Unreleased

- **New Settings layout:** a short list of sections (Appearance, Prices, Daily refresh, Backup and import, Server, About), each showing its current value. On a phone, tap one to open it full screen and use the back arrow (or your phone's back gesture) to return. On a computer the list stays on the left. On/off switches replace checkboxes, themes are small color chips, and the help text is shorter.
- On phones, card details, Settings, card shows, What's new and Add a card now fill the whole screen.
- **Name your server:** Settings → Server name. Type what you call the computer the binder runs on (like "BEN") and messages use it: "Saved on BEN", "Can't reach BEN". Left empty, they say "the server", so the binder makes sense for anyone running it.

## v3.0 (October 13, 2026)

- **Your data now lives in one database file** (`data/binder.db`, SQLite, built into Python, nothing to install).
  - Moves over by itself the first time v3.0 starts. Your old files are kept in `data/pre-sqlite-<date>/`, not deleted.
  - Saving a card or a day of prices only changes that one entry, so saves are much faster and can't clash with each other.
  - Changes that touch many things (a restore, a spreadsheet import) go in all together or not at all, even if the server loses power halfway.
  - Backups are still the same zip of JSON files: backups from older versions restore here, and backups from here restore in older versions.
  - Rolling back to an older version from Settings → About writes your data back out as files for it first, so nothing is lost.
  - Settings → About shows the database file and its size.
- **Opens faster, especially on your phone:** the server now squeezes the page and your binder data before sending them (gzip). The page is about 4 times smaller to download, and opening it again sends nothing at all if it hasn't changed.
- **The server works out price changes now:** the ▲▼ changes, biggest movers and gain/drop sorts come from a small summary the server sends, instead of your phone downloading every saved day of prices. That summary stays the same size however long your history gets. A card's price chart loads when you open that card.
- The updater can install versions made of more than two files (needed for upcoming changes).
- A built-in check (`tests/smoke_test.py`, 33 checks) runs before every release.

## v2.20 (October 12, 2026)

- **Safer updates:** before installing, the binder now test-starts the new version on its own (with a copy of your data) and checks that its pages answer. If it doesn't start, nothing is installed and you stay on your current version, with the reason shown.
- Updates and roll backs wait while a price refresh is running, so the restart can't stop the refresh halfway.
- A price refresh no longer undoes changes made while it runs. New price options, a restored backup, or card show towns changed during a scan are all kept.
- Card photos must be JPG, PNG, WebP, GIF or HEIC. If a photo is turned down, the reason is shown.
- Stats opens much faster once months of price history build up.
- If something unexpected goes wrong on the server, the page now gets an error message instead of waiting, and the details go to the container log.
- What's new on phones: each version's tags, change count and date fit without squeezing or cutting off the date. Dates leave out the year when it's this year.

## v2.19.3 (October 12, 2026)

- Scrolling fast inside Settings or any other floating window no longer scrolls the binder behind it. The page behind stays still while a window is open.

## v2.19.2 (October 12, 2026)

- The PokéCottage button only shows for Pokémon #1 to #251 (Gen 1 and 2), since those are the only master set pages PokéCottage has finished so far. Later Pokémon can still use **+ Add a card**.

## v2.19.1 (October 12, 2026)

- Fix: the "Check PokéCottage's list" button on the Missing a card? tile opened a page that doesn't exist. It now opens the right master set page, like pokecottage.com/pokemon-master-sets/totodile.

## v2.19 (October 12, 2026)

- **Price change period:** choose what the ▲▼ percentage on each card measures: 1 day, 7 days, 30 days, 90 days, 1 year or all time. Set it in Settings → Cards, or in the Filters panel on phones. It's saved on each device, and 7 days is the default.
- The same period is used by the biggest movers in Stats, the change column in the shopping list and the price chart on each card
- **New sorts:** biggest gain and biggest drop, over the chosen period
- Longer periods fill in over time: until the server has saved enough days of prices, the change covers the days it has, and the panel says how many

## v2.18.1 (October 12, 2026)

- Phones: the "may be missing cards" note moved out of the top bar to just above the cards, as one short line. The top bar shows only the menu, sprite, name and buttons again.
- Smaller Pokémon sprite on phones, so names like Totodile fit without being cut off.
- Fix: the custom card icon now stays in the header for binders that show the missing cards note.

## v2.18 (October 12, 2026)

- **Custom cards:** add a card the card database is missing, like a promo, trainer kit card or variant. Use **+ Add a card** on the **Missing a card?** tile at the end of the card list.
  - Give it a name, set, number and rarity, and optionally a picture.
  - **Prices:** paste the card's TCGplayer link and it gets recent sales and a price on the next refresh, like any other card. Or type a price yourself.
  - Custom cards have a **Custom** tag and work like normal cards: owned, condition, purchases, photos, spreadsheet import and backups. Open one to **Edit** or **Delete** it.
- A pencil icon with a count shows next to any binder with custom cards, in the sets menu and the binder's header.
- In Pokémon master set binders, the tile also links to that Pokémon's list on PokéCottage, to check for cards that might be missing.

## v2.17 (October 12, 2026)

- **Automatic backups:** the binder now saves a backup of all your data on the server before every update, rollback and spreadsheet import. If the backup can't be saved, the update is skipped.
  - See them in **Settings → Backup → Saved on the server**, with **Download** and **Restore** for each. The newest 10 update backups are kept.
- **Spreadsheet import:** in **Settings → Spreadsheet**, **Download template** gives you every card in the binder with what you own now. Fill in Qty, and optionally Condition, Your Cost and Notes, then **Import spreadsheet**.
  - Excel (.xlsx) and CSV both work, including the Neo Destiny tracker sheet.
  - You see what will change before anything is saved. Rows with a wrong card number or name are skipped and listed.
  - Importing only adds: it never marks a card as needed or removes purchases.

## v2.16.2 (October 12, 2026)

- Market prices are all in US dollars now. Cardmarket's price is converted from euros with the day's exchange rate (European Central Bank, via Frankfurter), and left out if the rate can't be fetched.
- Cardmarket numbers from the last refresh stay hidden until the next price refresh.

## v2.16.1 (October 12, 2026)

- Market prices: hide TCGplayer's "low" price when it's higher than the market price, since that's a data mistake on TCGdex's side.

## v2.16 (October 12, 2026)

- **Backup prices:** each price refresh also gets TCGplayer's market price and Cardmarket's 30-day average from TCGdex, a free card database (no key needed).
- When a card has no recent sales for your price options, it now uses TCGplayer's market price instead of keeping an old price. The card says when this happens.
  - Turn it off in **Settings → Price average** if you only want prices from real sales.
- Card details show a **Market prices** line as a second opinion. Cardmarket can mix 1st Edition and Unlimited for older sets, so treat it as rough.
- Test one card from the terminal (`python server.py --test neo4-107`) now shows the TCGdex prices too.

## v2.15.3 (October 11, 2026)

- **Security fix:** other websites can no longer make changes to your binder. Before, a web page open in the same browser could quietly send it commands (like adding a set or restoring a backup) if it knew the binder's address. Changes are now only accepted from the binder's own page.
- The binder only answers to IP addresses, localhost, one-word names and home or Tailscale names. To reach it by another name (like a reverse proxy), add that name to the `BINDER_HOSTS` container setting.

## v2.15.2 (October 11, 2026)

- Sets menu: swipe left to close it on a touch screen. Scrolling up and down still scrolls the menu.

## v2.15.1 (October 11, 2026)

- Phone filters panel: swipe down to close it (from the top of the panel, or anywhere when it isn't scrolled), without the browser's pull-to-refresh kicking in
- The panel is only as tall as its contents, so there's room above it to tap and close

## v2.15 (October 11, 2026)

- **Tidier phone layout:** on phones, the card filters fold into one row: the search box and a **Filters** button. The button shows how many filters are on, and a short line under it says what you're seeing (like "Need · 72 of 113 cards").
- Filters opens a panel from the bottom with Show (All / Need / Owned), Rarity (or Set in master set binders) and Sort as tap-friendly buttons, a Reset, and "Show N cards" to close it. Changes apply as you tap.
- Computers keep the full filter row as before

## v2.14.1 (October 11, 2026)

- Refresh prices asks first, showing when prices were last updated and about how long a refresh takes, so a stray tap doesn't start one

## v2.14 (October 11, 2026)

- **Sets menu animation:** the menu grows out from the left. On a computer it sits beside the binder and pushes the page over (the cards re-flow to fit) instead of covering it; tap the menu button again, Close, or Esc to slide it away. On a phone it slides in over the page.
- More space between "Your sets", the All binders box and the list
- Animations turn off if your device is set to reduce motion

## v2.13.1 (October 11, 2026)

- Floating windows (Settings, Card shows, What's new, card details) have a title bar: the name on the left and a close button on the right stay put at the top while everything below scrolls

## v2.13 (October 11, 2026)

- **What's new:** the version number now shows at the bottom of the sets menu. Tap it to read the release notes, grouped into newer versions, this version line (like everything since v2.13) and earlier releases. Each version opens to show its changes, with Installed and Latest tags and a link to all releases on GitHub.
- **Update notice:** when a newer version is on GitHub, a small dot appears on the menu button and the version line says which one is available. Tap through to What's new and use Install update (it still asks you to confirm). The binder checks about once an hour and never installs anything by itself.
- Floating windows: Close sits in a solid bar across the top with more room from the edge, so text no longer scrolls underneath or beside it

## v2.12 (October 11, 2026)

- Card details open as a floating window in the middle of the screen, like Settings and Card shows (was a side panel)
- Floating windows scroll instead of squeezing their contents when there is a lot in them (the card tabs could shrink to a thin line)

## v2.11.2 (October 11, 2026)

- Dropdown menus everywhere: the arrow sits further in from the right edge and matches the theme colors

## v2.11.1 (October 11, 2026)

- Floating windows: the scroll bar no longer shows arrow buttons that run into the rounded top and bottom corners (Chrome and Edge)

## v2.11 (October 11, 2026)

- Floating windows (Settings, Card shows): the scroll bar is slimmer and sits inside the rounded corners instead of running over them
- Close stays in the top corner while you scroll

## v2.10 (October 11, 2026)

- Settings opens as a floating window in the middle of the screen, like Card shows. On a computer the themes sit two per row.

## v2.9 (October 11, 2026)

- Add a set / Add a Pokémon: even spacing between the title, the Set/Pokémon switch, the search box and the list, so the search box's highlight no longer touches the switch

## v2.8 (October 11, 2026)

- Card shows opens as a floating window in the middle of the screen instead of a side panel
- Show titles and descriptions no longer repeat the town and date (already shown on the left and under each name)
- Pokémon / TCG filter stays on one line on phones

## v2.7 (October 11, 2026)

- **Loading bars** that show real progress (how many steps are done out of the total):
  - Price refresh, under the status line at the top
  - Card image downloads after adding a set or Pokémon
  - Making the Pokémon list (Add a Pokémon)
  - Card show scans
- When the server doesn't know the total yet, the bar slides back and forth until it does

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
