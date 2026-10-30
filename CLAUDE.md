# Pokemon Binder (Neo Destiny Tracker)

A self-hosted Pokémon card collection tracker. `server.py` is the server
(Python, standard library only) and `index.html` is the page, with its styles
and code in `app/` (`style.css`, plus `*.js` files that `index.html` loads in
order and that share one scope). The owner is
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
- Settings → Server name lets the owner type a name, so their own app may
  show "Saved on BEN". That's fine. But examples, help text, the changelog
  and screenshots use "the server" or a made-up name (like "Attic").

## Screen sizes
- Every change that touches the page must work and fit, with nothing cut
  off or overlapping, on:
  - a 1080p desktop (1920×1080)
  - a 4K desktop (3840×2160)
  - the owner's phone, a Pixel 11 Pro (about 412×915 in the browser)
- Before saving a page change, run the app and check all three.

## README screenshots and the demo binder
- README screenshots come only from a demo binder: a separate copy of the app
  with made-up cards, purchases and sellers, outside this repo. Never from the
  owner's real binder.
- Keep the demo binder's program files the same as the latest release, and
  retake the screenshots when a release changes what they show.

## Program files
- `APP_FILES` in `server.py` lists the files an update installs. When you add
  a new program file, add it there too, or updates won't deliver it.

## Releasing (only when the owner says "release" or "push it")
1. Set `APP_VERSION` in `server.py` to the new version.
2. Rename `## Unreleased` in `CHANGELOG.md` to `## v<version> (<date>)`.
   The app only reads headings in that form.
3. Run `python3 tests/smoke_test.py` (on Windows: `python tests/smoke_test.py`),
   and after feature releases also `tests/cleanup_check.py`. All must pass.
   Also run `tests/api_check.py`: it compares every API answer with
   `tests/api_answers.json`. If an answer changed on purpose, save the new
   ones with `--save`; if not, it's a bug.
4. Merge `next` into `main` and push.
