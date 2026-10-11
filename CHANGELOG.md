# Changelog

Versions go up by 0.1 for each app update (new features or fixes) and by a whole number for big changes, like a redesign or a change to how data is stored. Changes that don't touch the app, like README edits, don't get a new number.

The binder shows these in **Settings → About → Check for updates**.

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
