# Pokemon Binder (Neo Destiny Tracker)

A self-hosted Pokémon card collection tracker. `server.py` is the server
(Python, standard library only) and `index.html` is the page. The owner is
not a programmer.

## Working with the owner
- Explain everything in plain language, with no unexplained jargon.
- Work one step at a time. After each step, stop and wait for the owner to
  reply ("done", a result, or an error) before going on.

## Branches
- `main` is the released app. Servers install updates from `main`.
- `next` is work in progress. Do all work on `next`.
- Never commit to `main` directly. Only release (merge `next` into `main`)
  when the owner says "release" or "push it".

## Versions and the changelog
- The version is `APP_VERSION` in `server.py`, and every version has an
  entry in `CHANGELOG.md`.
- Three kinds of version bump:
  - Last number (3.27.2 → 3.27.3): small fixes and touch-ups
  - Middle number (3.27 → 3.28): new features or bigger changes
  - Whole number (3.x → 4.0): big changes, like a redesign or a new way of
    storing data. Needs the owner's OK first.
- Keep a `## Unreleased` section at the top of `CHANGELOG.md` (under the
  intro) and add each change to it as you go, in the same plain style as
  the existing entries. On release, rename it to the new version and date,
  e.g. `## v3.28 (October 24, 2026)`.
- Changes that don't touch the app (like README edits) don't get a new
  version number.

## Updates
- The app never updates by itself. The owner picks the update in
  Settings → About and confirms it.
- The server makes a backup before installing an update.
- The version pill links to that version's notes in the CHANGELOG.
- Don't change any of this without the owner's OK.

## Public repo: keep it clean
This repository is public. Never commit:
- passwords, API keys or tokens
- server IP addresses
- Tailscale machine or network names (use placeholders like
  `<machine>.<your-tailnet>.ts.net`)
- the owner's collection data (`data/`, `backups/`, `previous/`, `binder.db`,
  photos). The collection stays on the server, never in the repo.

## Wording in the app
- Text in the app says "the server", never "BEN" (the owner's server name).

## Before a release
- Run `python3 tests/smoke_test.py`, and after feature releases also run
  `python3 tests/cleanup_check.py`.
