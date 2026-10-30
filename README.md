# Pokemon Binder

> [!WARNING]
> **This is a fully vibe-coded project.** I'm not a programmer. I had an idea for tracking my own card collection and built this with an AI assistant, for personal use on my home server. It works for me, but it hasn't been reviewed by an experienced developer, and it comes with no support or guarantees. Use it at your own risk, and don't expose it to the open internet.

A self-hosted Pokémon TCG collection tracker: one small Python server (standard library only) and one web page, for your home server and your phone.

- **Binders your way:** any English set, a Pokémon master set (every card of one Pokémon, like all the Totodile cards), or your own mix (Favorites, Trade pile). Owned cards in color, needed ones in greyscale.
- **Real binder pages:** lay cards out 4, 9, 12 or 16 to a page, with a cover. **Find a card** searches every English card by name, number (like `80/111`) or set.
- **Prices from recent sales:** TCGplayer's newest sales for each condition (LP and MP by default), with TCGdex market prices as a backup. Daily refresh, price history, biggest movers, a shopping list with a budget, and an upgrades list.
- **At the card show:** card show mode lists every card you still need, with a big **Got it** button. Type a vendor's asking price to see if it's a good deal, what to offer and when to walk away. Scan a PSA slab's label to check it's real and see recent sales for that grade.
- **Your copies:** condition, notes, front and back photos, and a purchase log (price, place, seller). Zoom in on a holo and it shimmers like the real card.
- **Phone app (Android):** install it, open it with no signal, mark cards owned offline, sync when you're back.
- **Safe and private:** privacy mode (eye button), automatic backups, one-file backup and restore, spreadsheet import and export (with price trends), and updates only when you choose.

Also: custom cards for anything the card database is missing, upcoming card shows in your towns, and five dark themes.

## Screenshots

**Home.** A shelf of all your binders, each with its cover Pokémon and how complete it is, plus Find a card and the cards you added most recently.

![The home page with a shelf of binders](screenshots/home.png)

**The binder.** Owned cards in color, cards you still need in greyscale, with totals at the top and each card's price trend. Filter by owned or needed, rarity, or name, and sort by number, rarity, Pokédex number or value.

![The binder's main page](screenshots/binder.png)

**Pages.** Lay out a binder like a real one, page by page, with an inside cover featuring one of the set's best cards. Tap the round buttons to pick which Pokémon is on the cover.

![The Pages view with the inside cover and page 1](screenshots/pages.png)

**Card details.** The price to buy one, from recent sales, with its trend and how it's worked out a tap away. Type what a vendor is asking to see if it's a good deal, what to offer and when to walk away. Below are the newest sales for every condition, so you can see whether a different condition is worth it.

![Card details with prices and recent sales](screenshots/card-details.png)

**Your copy.** Copies owned, condition, a purchase log with where you bought it and from whom (one tap for eBay, TCGplayer, a card show or a place you've used before), notes, and photos of your own card.

![Card details, My copy tab](screenshots/my-copy.png)

**Privacy mode.** Tap the eye button: every card shows in color, Owned/Need tags disappear, your totals blur, and the Shopping list, Upgrades and Stats tabs are locked, so nobody looking over your shoulder can tell what you own.

![Privacy mode turned on](screenshots/privacy-mode.png)

**Settings.** Themes, price options, the daily price check, backups, updates and more.

![Settings](screenshots/settings.png)

## How was this possible?

I don't know how to code. I built this by describing what I wanted to an AI assistant, testing each version, and asking for changes one at a time. If you'd like to build something similar for yourself, running on your own computer and opening on your phone, I wrote up how it works in beginner terms, including what Tailscale is and how to set it up.

**[Read: How I built this without knowing how to code](docs/how-this-was-made.md)** · [PDF version](docs/how-this-was-made.pdf)

Your collection, purchases, photos, and prices are stored only on the machine running the binder. This repository holds program files only.

## Program files

| File | What it is |
|---|---|
| `server.py` | The web server: starts the binder and runs the files in `binder/` |
| `binder/` | The rest of the server, one file per part: storage, cards, prices, PSA, pictures, card shows, spreadsheets, backups, phone sync, web pages and updates (since v4.0) |
| `index.html` | The binder page (its layout) |
| `app/` | The page's styles (`style.css`) and code, one file per part: the grid, card details, Pages, card show mode and so on (since v4.0) |
| `fonts.css` | The page's fonts, built in so the binder doesn't ask Google for them (since v3.5) |
| `sw.js` | Keeps a saved copy of the binder on your phone so the app opens offline |
| `icon-192.png`, `icon-512.png` | The phone app's icons |
| `fonts-OFL.txt` | The fonts' free license (not installed on your server) |
| `seed_prices.json` | Starting Neo Destiny prices, only used on a brand-new install |
| `tests/smoke_test.py` | Checks the binder before a release: `python3 tests/smoke_test.py` (not installed on your server) |
| `tests/cleanup_check.py` | Lists leftover code nothing uses and names used twice, after each feature release: `python3 tests/cleanup_check.py` (not installed on your server) |

## Your data (never in this repository)

Stored in `data/` next to `server.py`:

| Path | What it holds |
|---|---|
| `binder.db` | Everything you enter and every price: binders, settings, copies owned, condition, purchases, sellers, notes, latest prices, one saved price per card per day, price options, shopping lists, card shows. One SQLite database file (since v3.0) |
| `favicon` | Your tab icon, if you picked one |
| `catalog.json`, `dex_index.json`, `card_index.json`, `fx.json` | Downloaded lists (all English sets, the Pokédex index, every English card for Find a card, the euro rate). They download again by themselves |
| `unown/`, `art/`, `dexno/` | Downloaded pictures and Pokédex numbers for binder covers and master sets. They download again by themselves |
| `sets/<set id>/images/` | Card pictures: `s/` holds the small ones for the grid, full-size scans are saved when you open a card. Pictures download as you look at them; a binder kept for an hour fills in the rest in the background |
| `sets/<set id>/photos/` | Your photos (front = `<number>`, back = `<number>_back`) |
| `sets/<set id>/layout.json`, `logo.png` | Your Pages layout and cover pick, and the set's logo |
| `pre-sqlite-<date>/` | Your old JSON files from before v3.0, set aside (not used any more) |

Backups live in `backups/` and old versions in `previous/`, both next to `server.py`. Backups (Settings → Backup) are a zip of plain JSON files, so they open in any text editor and restore in both older and newer versions. To look inside `binder.db` itself, use a viewer like DB Browser for SQLite.

## Running it with Docker (Unraid example)

| Setting | Value |
|---|---|
| Image | `python:3.12-alpine` |
| Port | any free port on the host → `8080` in the container |
| App data | a folder on the host → `/app` (put the program files from the table above in it) |
| Extra parameters | `-w /app` |
| Post arguments | `python -u server.py` |
| Variable (optional) | `BINDER_HOSTS`: extra names the binder answers to, like a reverse proxy name (IP addresses, one-word names and Tailscale names already work) |

Without Docker: put the program files in a folder and run `python server.py` (Python 3.9 or newer), then open `http://localhost:8080`.

## Running it with Docker Compose

1. Make a folder for the binder, with a `binder` folder inside it. Put the program files from the table above in `binder` (on GitHub: **Code → Download ZIP**, then copy them out).
2. Next to the `binder` folder, make a file called `docker-compose.yml`:

   ```yaml
   services:
     pokemon-binder:
       image: python:3.12-alpine
       container_name: pokemon-binder
       working_dir: /app
       command: python -u server.py
       ports:
         - "8765:8080"            # open the binder on port 8765
       volumes:
         - ./binder:/app          # program files, plus your data/ and backups/ once it runs
         - /etc/localtime:/etc/localtime:ro   # the server's clock, so the nightly price check runs at night
       # environment:
       #   BINDER_HOSTS: binder.example.com   # only if you use a reverse proxy name
       healthcheck:
         test: ["CMD", "wget", "-qO-", "http://localhost:8080/api/health"]
         interval: 2m
         timeout: 10s
       restart: unless-stopped
   ```

3. In that folder, run:

   ```bash
   docker compose up -d
   ```

4. Open `http://<your server's address>:8765` (or `http://localhost:8765` on the same computer).

Your collection is saved in `binder/data/` and backups in `binder/backups/`, so they survive `docker compose down` and new images. Updates still only install from **Settings → About**; restarting the container never installs one.

## Phone app (Android)

The binder can be installed as an app on Android phones with Chrome. It isn't set up for iPhone. When it opens, it shows its icon on a launch screen while your binders load (your own icon, if you set one in Settings). It needs a secure (https) address, which [Tailscale](https://tailscale.com/kb/1312/serve) can provide for free inside your own Tailscale network:

1. In the Tailscale admin console, under **DNS**, turn on **MagicDNS** and **HTTPS Certificates**.
2. On the computer running the binder, run `tailscale serve --bg 8765` (use your binder's port). Tailscale prints the https address, like `https://<machine>.<your-tailnet>.ts.net`. If that machine already uses https for something else (Unraid's own Tailscale setting does), use `tailscale serve --bg --https=8443 8765` and add `:8443` to the address.
3. On your phone (with Tailscale on), open that address in Chrome and tap **Install** (or Settings → Phone → Install).

This keeps the binder inside your Tailscale network; nothing is opened to the internet.

The app keeps a saved copy of your binders on the phone, so it opens with no signal. Offline you can mark cards owned and add purchases (price, where, seller); when the connection is back, the binder lists those changes and sends them only after you tap **Sync**, with **Undo last sync** if needed.

## Updating

Updates only install when you choose them: **Settings → About → Check for updates** shows what's new and asks before installing anything (no restart needed). Restarting the container never installs updates. No key or password is needed.

Settings → About shows the installed version, any update problem, and up to 3 previous versions you can roll back to. Version history is in [CHANGELOG.md](CHANGELOG.md).

Safety nets:
- Before installing, the new version is test-started on its own with a copy of your data. If it has an error or doesn't start, nothing is installed and the current version keeps running.
- A backup of your data is saved first (Settings → Backup → Saved on the server). A daily backup is also saved every day and the last 7 are kept.
- The binder checks itself every 2 minutes and restarts if it stops answering for about 6 minutes. **Settings → About → Status** shows the last price check, last backup, storage used, free space and any problems in the last day. `/api/health` answers for outside uptime monitors.
- The last 3 versions are kept in `previous/` next to `server.py`. Rolling back to a version from before v3.0 writes your data back out as the files it uses.
- Each version lists the files it needs in its `server.py` (`APP_FILES`), so new files arrive with the update.

Optional environment variables:

| Variable | Default | Use |
|---|---|---|
| `GITHUB_REPO` | `g-i-n-g-y/pokemon-binder` | Where updates come from. Set it empty to turn GitHub updates off. |
| `GITHUB_BRANCH` | `main` | Branch to update from |
| `GITHUB_TOKEN` | (none) | Only needed if you update from a private copy |
| `BINDER_UPDATES` | `/updates` | Folder used for updates when `GITHUB_REPO` is empty |

## Price test for one card

```bash
docker exec <container name> python server.py --test neo4-1
```

## Credits and inspiration

- **[Tracearr](https://github.com/connorgallopo/Tracearr)** by Connor Gallopo inspired the What's new window (versions grouped with Installed and Latest tags, opened from the version number), the update notice, and the sets menu that slides out and pushes the page over. I showed Claude (the AI assistant this app is built with) screenshots and a screen recording of Tracearr, and it wrote this app's own versions. None of Tracearr's code was used.
- Card lists: [PokemonTCG/pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data); card images and set logos from the [Pokémon TCG API](https://pokemontcg.io)
- Pokémon sprites and artwork (covers, master sets, Unown letters): [PokeAPI/sprites](https://github.com/PokeAPI/sprites)
- PSA slab checks: PSA's public cert pages
- Prices: TCGplayer recent sales, market prices from [TCGdex](https://tcgdex.dev) (TCGplayer and Cardmarket), and graded sales from PriceCharting (when it lets the server in; it often blocks home servers)
- Euro to US dollar rate: [Frankfurter](https://frankfurter.dev)
- Card show listings: [TreasureHunter.show](https://www.treasurehunter.show)
- Master set checklists linked from Pokémon binders: [PokéCottage](https://pokecottage.com)
- Fonts: [Bricolage Grotesque](https://github.com/ateliertriay/bricolage) and [IBM Plex](https://github.com/IBM/plex), free under the SIL Open Font License (see `fonts-OFL.txt`)

Pokémon and all related names and images are trademarks of Nintendo, Creatures and GAME FREAK. This is a personal, unofficial project.
