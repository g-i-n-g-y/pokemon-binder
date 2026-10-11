# Changelog

Versions go up by 0.1 for each app update (new features or fixes) and by a whole number for big changes, like a redesign or a change to how data is stored. Changes that don't touch the app, like README edits, don't get a new number.

The binder shows these in **Settings → About → Check for updates**.

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
