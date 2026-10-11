# Pokemon Binder

> [!WARNING]
> **This is a fully vibe-coded project.** I'm not a programmer. I had an idea for tracking my own card collection and built this with an AI assistant, for personal use on my home server. It works for me, but it hasn't been reviewed by an experienced developer, and it comes with no support or guarantees. Use it at your own risk, and don't expose it to the open internet.

A self-hosted Pokémon TCG collection tracker. One small Python server (standard library only) and one web page.

- Any English set: card lists from [PokemonTCG/pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data), card images downloaded locally
- Owned cards in color, needed cards in greyscale; tap **Need** to mark a card owned
- Prices from recent TCGplayer sales: separate LP and MP averages (Unlimited, English), plus averages for every condition
- Daily automatic price refresh at a time you choose, plus a manual refresh button
- Price history, biggest movers, shopping list with a budget
- Purchase log with date, price, place, and seller handle (Instagram, TikTok, Whatnot, eBay, and more)
- Front and back photos of your own copies
- Privacy mode (eye button): shows every card in color with no Owned/Need tags, blurs cards owned and money totals, hides purchases
- Five dark themes; works on phones

## Screenshots

**The binder.** Owned cards in color, cards you still need in greyscale, with totals at the top.

![The binder's main page](screenshots/binder.png)

**Privacy mode.** Tap the eye button: every card shows in color, Owned/Need tags disappear, and your totals blur, so nobody looking over your shoulder can tell what you own.

![Privacy mode turned on](screenshots/privacy-mode.png)

**Card details.** Tap a card for its LP and MP prices, copies owned, condition, purchase log with sellers, and photos of your own copy.

<img src="screenshots/card-details.png" alt="Card details panel" width="360">

## How was this possible?

I don't know how to code. I built this by describing what I wanted to an AI assistant, testing each version, and asking for changes one at a time. If you'd like to build something similar for yourself, running on your own computer and opening on your phone, I wrote up how it works in beginner terms, including what Tailscale is and how to set it up.

**[Read: How I built this without knowing how to code](docs/how-this-was-made.md)** · [PDF version](docs/how-this-was-made.pdf)

Your collection, purchases, photos, and prices are stored only on the machine running the binder. This repository holds program files only.

## Program files

| File | What it is |
|---|---|
| `server.py` | The web server |
| `index.html` | The binder page |
| `seed_prices.json` | Starting Neo Destiny prices, only used on a brand-new install |

## Your data (never in this repository)

Stored in `data/` next to `server.py`:

| Path | What it holds |
|---|---|
| `sets.json` | Which sets are in the binder |
| `settings.json` | Refresh time and other settings |
| `catalog.json` | All English sets (refreshed weekly) |
| `sets/<set id>/collection.json` | Copies owned, condition, purchases, sellers, notes |
| `sets/<set id>/prices.json` | Latest prices, including per-condition averages |
| `sets/<set id>/history.json` | One saved price per card per day |
| `sets/<set id>/images/` | Card images |
| `sets/<set id>/photos/` | Your photos (front = `<number>`, back = `<number>_back`) |

## Running it with Docker (Unraid example)

| Setting | Value |
|---|---|
| Image | `python:3.12-alpine` |
| Port | any free port on the host → `8080` in the container |
| App data | a folder on the host → `/app` (put `server.py` and `index.html` in it) |
| Extra parameters | `-w /app` |
| Post arguments | `python -u server.py` |

Without Docker: put `server.py` and `index.html` in a folder and run `python server.py` (Python 3.9 or newer), then open `http://localhost:8080`.

## Updating

The binder updates itself from this repository. No key or password is needed.

- **Settings → About → Check for updates** (no restart needed), or
- **Restart** the container (it checks for updates on every start).

Check for updates shows what's new and asks before installing. Settings → About shows the installed version, any update problem, and up to 3 previous versions you can roll back to. After a rollback, automatic updates pause until you install an update yourself. Version history is in [CHANGELOG.md](CHANGELOG.md).

Safety nets:
- A new `server.py` with an error is skipped entirely, and the current version keeps running.
- The last 3 versions are kept in `previous/` next to `server.py`.

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
