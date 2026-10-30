# Changelog

Version numbers, starting after v2.11:

- **Whole number** (3.0): big changes, like a redesign or a change to how data is stored
- **Middle number** (2.12): new features or bigger changes you'll notice
- **Last number** (2.11.1): small fixes and touch-ups, like spacing or a scroll bar

Versions up to v2.11 went up by 0.1 for every update, including small fixes, and keep their numbers. Changes that don't touch the app, like README edits, don't get a new number.

The binder shows these in **Settings → About → Check for updates**.

## Unreleased

- **Upgrades shows which conditions are picked:** each picked condition (MP, HP, DMG) has a ✓, unpicked ones are dimmed, and a thin line separates the buttons, so two picked ones no longer look like one.
- **Shopping list without a column of zeros:** the price-change column only shows once at least one card on the list has actually gone up or down, instead of "0.0%" on every row.
- **Stats without a half-empty box:** when no prices have moved yet, Spending per month uses the full width and Biggest movers shrinks to one short line underneath. Once prices move, they sit side by side again.

## v3.35.1 (October 26, 2026)

- **Pick the site first when adding a seller:** the Seller pop-up now shows the sites (Instagram, TikTok, Whatnot, eBay and more) as buttons under the search box, so you can pick where they sell before typing their name. Pasting a link still picks the site for you.
- **Where works on phones:** the Where box under Purchases now has tappable buttons (eBay, TCGplayer, card show and places you've used before) instead of a dropdown that ended up on the keyboard. The PSA slab check's card suggestions work the same way.
- **Where each sale happened:** in card details, every recent sale now shows where it sold, as a link. Raw sales say **TCGplayer** and open the card's TCGplayer page, which has its sales history (TCGplayer doesn't link single sales). Graded sales say **eBay** and open the actual listing when PriceCharting links it, otherwise **PriceCharting** opens the card's page there.

## v3.35 (October 25, 2026)

- **Vendor price check uses price history:** once the server has saved at least 5 days of prices over 2 weeks or more, the **Open at** and **Walk away above** numbers come from the card's last 90 days instead of a fixed percentage. You open near its lowest price and walk away a little over its usual price, so a short spike never sets what you pay. Cards without enough history keep the old rule.
- **Wait or buy now:** the check tags a card **Wait if you can** when it's 15% or more over its usual price or jumped 15% this week, and **Good time to buy** when it's under its usual price.
- **Know your numbers before you ask:** before you type a price, the box already shows what to aim for and when to walk away. Works in card details (Prices tab) and in the card show **Got it** sheet.

## v3.34 (October 25, 2026)

- **Pick binders for the spreadsheet:** Download spreadsheet (Settings → Backup and import) now lets you pick which binders go in the Excel file, instead of always downloading all of them. A single binder's file is named after it.
- **Price trends in the spreadsheet:** new columns show each card's price change over 7, 30 and 90 days and the date of its last sale. Handy for spotting cards that are climbing, or for asking an AI to suggest what to buy first.

## v3.33 (October 25, 2026)

- **Vendor price check:** a new **Vendor's price** box in card details (Prices tab). Type what a seller is asking and pick the condition of their copy, and it tells you whether it's a **Good deal**, **Fair** or **High** compared with recent sales, what to **open at** (about 85% of recent sales) and when to **walk away** (about 15% over). If the price has climbed over the last 30 days, both numbers move closer to the sticker; if it's dropped, they go lower.
- **Works in card show mode too:** in the **Got it** sheet, type the vendor's price and pick the condition to see the same advice, then change the price to what you paid before saving.
- **What you usually pay:** the check also shows how far over (or under) the price you've usually paid, worked out from your purchase log, split into cards under $20 and cards $20 and up. Hidden in privacy mode.
- Uses the price the server already checks every night, so there's nothing to set up. If a card's price is old, it says so and suggests checking eBay sold first.
- **PSA slab check backup screen is easier:** tapping a grade before typing the card now jumps to the card box and says what's missing, instead of doing nothing. The card box also suggests cards as you type.

## v3.32.3 (October 25, 2026)

- **PSA slab check works without PSA's approval:** PSA only lets approved customers use its lookup service, so the server now reads PSA's public cert page instead (the one anyone can open). The access code in Settings → Prices is now optional, for when PSA approves you.
- **A backup plan when PSA's page can't be read:** the check then opens PSA's page for the slab on your phone. Type the card and tap the grade on the label, and the eBay sold and PriceCharting buttons work from there.

## v3.32.2 (October 25, 2026)

- **Clearer PSA slab check errors:** when PSA turns a check away, the message now says why (a wrong access code, PSA's firewall, or the daily limit) and shows PSA's error number. It's also listed under Recent problems in Settings → About.
- **PSA slab check asks PSA more plainly:** the server now names itself as the binder app instead of posing as a web browser, which firewalls are less likely to block.

## v3.32.1 (October 25, 2026)

- **Slab scanning works better:** Scan the label now opens a live camera view in the pop-up that keeps trying as you aim, so you can just move closer to the small barcode on the label. Photos are also read in enlarged pieces, so a barcode that's small in the photo can still be found.
- **Find a card fits on phones:** it now fills the screen like the other pop-ups, instead of leaving a gap on the right.

## v3.32 (October 25, 2026)

- **Check a PSA slab:** scan the barcode or QR code on a PSA slab's label (or type the cert number) to see if it's real. It shows the card, grade, how many PSA has graded at that grade and higher, and PSA's own photos of the slab, so you can compare them with the one in your hand. Find it in the ☰ menu, or the scan button next to the search box in card show mode.
- **Recent sales for that grade:** after a check, one tap opens eBay sold listings for that exact card and grade (newest first, 1st Edition or Unlimited to match the slab), PriceCharting's prices for every grade in a new tab, or PSA's page for the slab.
- **Matches your binders:** the check finds the card in your binders and says whether you own or need it, with the page it's on. Tap it to open the card.
- **One-time setup:** paste a free PSA access code in **Settings → Prices**. It stays on the server. PSA allows about 100 checks a day, and each slab is only looked up once.

## v3.31.2 (October 25, 2026)

- **Reload the app moved:** the Reload button is now in **Settings → About**, next to Check for updates.

## v3.31.1 (October 25, 2026)

- **Set map removed:** the tiny binder pages above the search box on the Cards tab are gone, so the cards start higher up. The Pages tab still shows every page.

## v3.31 (October 25, 2026)

- **Set map:** under the totals on a binder's Cards tab, a row of tiny binder pages shows every pocket with its card's picture, in color if you own it and grey if you still need it. It follows your Pages layout (pockets per page, order, cards you've moved). Point at a pocket to see the card, or tap a page to open it in Pages. On phones it's one row you swipe sideways. In privacy mode every pocket shows in color.

## v3.30 (October 25, 2026)

- **Bigger on 4K screens:** on very wide screens the binder uses much more of the width, with bigger cards, a wider shelf of binders on My binders, and bigger binder pages that still fit the window's height. 1080p screens and phones look the same as before.

## v3.29.1 (October 24, 2026)

- **"Updated to" window floats on phones:** the short list shown after an update is now a card in the middle of the screen with the page dimmed behind it, instead of filling the whole screen. A long list scrolls inside the card.

## v3.29 (October 24, 2026)

- **What changed, after each update:** the first time you open the binder on a new version, a short **Updated to v…** window lists the headline of each change since the version that device last had. **Full notes** opens What's new. Close it with ✕, **Got it**, or a tap outside the window. Each phone and computer shows it once.

## v3.28 (October 24, 2026)

- **No more ALL-CAPS labels:** headings and small labels like "Your binders", "Cards owned", "Unlimited" and the Owned/Need tags now use normal capitals, so they're calmer and easier to read.
- **Smaller Add a binder button:** on My binders, **Add a binder** is now a small button next to Edit instead of a big empty tile on the shelf. With no binders yet, the big tile still shows so you know where to start.
- **Empty spots tell you what to do:**
  - When filters or a search hide every card, the binder says why (like "You haven't marked any cards owned here yet") with a **Show all cards** or **Clear filters** button.
  - A card marked owned without a price shows **Price not added yet** instead of "$0.00 total", and "· 2 without a price" when only some purchases have one.
  - An empty purchase list, the Upgrades tab and the value chart in Stats now say what fills them in.
- **Prices tab leads with one number:** a card's Prices tab opens with a big **Price to buy one** and where it comes from, then the price chart. The LP and MP averages and the TCGdex market prices moved under **How this price is worked out**, which opens with a tap.

## v3.27.3 (October 24, 2026)

- **Server name example:** the help text under Settings → Server name now uses a made-up example name instead of the name of the server this binder was built on.

## v3.27.2 (October 21, 2026)

- **Scrolling the page numbers no longer turns the page:** on phones, swiping the row of page-number buttons sideways in Pages only scrolls the row. Before, the swipe also counted as "turn the page" and flipped pages while you scrolled. Swiping on the page itself still turns pages.

## v3.27.1 (October 21, 2026)

- **Pages are numbered 1, 2, 3, 4…:** every side of a sheet now has its own page number instead of "Page 1, front / Page 1, back". This shows in the Pages view, the page buttons on phones (one per page now), a card's binder spot ("Page 3, row 1, pocket 2") and card show mode's By page headings.

## v3.27 (October 19, 2026)

- **Binder cover backgrounds:** **Edit** on My binders opens a **Binder covers** window where you pick the background behind every cover's Pokémon: Sunburst (the original), Spotlight, Poké Ball, Holo or Halftone. Each choice shows as a preview of your own cover. It applies to the home page covers and the inside cover in Pages, and is saved on that device like the app's colors.
- Reordering, renaming and removing binders is still one tap away, under **Reorder, rename or remove binders** in the same window.

## v3.26 (October 18, 2026)

- **Backups take much less space:** automatic backups made before an update, a phone sync or a spreadsheet import no longer include a copy of your card photos, since those never change photos. Backups before a restore or a fresh start still include them, and so does one daily backup a week. **Download backup** in Settings still includes everything. Restoring a backup without photos keeps the photos you have. The backups list says which ones are "without photos".
- **Temporary files are cleaned regularly:** leftovers from an interrupted download, update check or backup are now removed every 30 minutes once they're over 6 hours old, not only when the server restarts.
- **Status shows backup space:** Settings → About → Status has an Automatic backups line with how many are kept and the space they use.
- **Fresh starts open on My binders:** after installing an update, restoring a backup, Reload the app or Clear saved copy, the app opens on My binders instead of the binder or card show screen you were on.

## v3.25 (October 18, 2026)

- **Seller pop-up:** the seller is now one button ("Choose seller") with a ✕ to clear it, in both card show mode and a card's My copy. Tapping it opens a **Seller** pop-up with:
  - a search box
  - Scan vendor QR
  - everyone you've bought from, most recent first, with how many times and when
- **New sellers in the pop-up:** if what you type isn't on the list, an **Add as a new seller** box appears below it, where you pick their site. A pasted link (like a Linktree) picks the site by itself.
- The pop-up stays the same size however many sellers you build up, and replaces the long Past seller list from v3.24.

## v3.24 (October 18, 2026)

- **Past sellers:** when you add a purchase, a **Past seller** list shows everyone you've bought from across all your binders, most recent first, with how many times. Picking one fills in the site and username. It's in both places you log purchases: the Got it screen in card show mode, and My copy in a card's details. In card show mode it works with no signal too.

## v3.23.2 (October 18, 2026)

- **Card show mode, grouped:** By page puts a heading over each page side (like "Page 1, back · 7 left · $855"), so you can see how many cards are left on each page and what they'd cost. By binder does the same per binder. Values in the headings are hidden in privacy mode.

## v3.23.1 (October 18, 2026)

- **Card show mode sorting:** one **Price** button with an arrow. Tap it for lowest first (↑), tap again for highest first (↓). **By page** is new: cards in the order they sit in your binder pages, with each card's spot shown (like "Page 5, back"), so you can work through a binder page by page. By binder stays.
- **Card show mode header:** the calendar (card shows), privacy and settings buttons are now at the top, the same as on My binders. Picking which binders you're working on moved to a **Change** link next to the binder names.

## v3.23 (October 18, 2026)

- **One look for every pop-up:** every window and settings page now follows the same rules:
  - the same title bar, with the title on the left, a close button on the right, and a back arrow when you're one level in
  - bold section headings
  - rounded grouped rows for settings
  - switches for on/off
  - full-width button rows
  - the main button on the right on computers, and full width on phones
- **Add a binder** uses the same title bar as Settings, and is called "Add a binder" everywhere (it said "Add a set").
- **Card shows** window rebuilt in the same style: the weekly check is a switch, towns sit in a grouped row, and Save towns is in the usual spot.
- **About → Recent problems** gives a short plain summary (like "card shows (6)"), with the full messages behind **Show details**.
- **Card show mode:** card pictures load now (they were silently failing), and tapping a card's picture or name shows it full screen, the same as in card details.

## v3.22 (October 18, 2026)

- **Card details on phones, reworked:** a smaller card picture on the left with the name, number, rarity, binder spot and "You own this card" beside it, instead of everything stacked and centered. The Prices, Recent sales and My copy tabs now start right below, so prices show as soon as a card opens. The eBay sold, PriceCharting and TCGplayer buttons moved into the Prices tab.
- **Tap the picture to see it big:** tapping the card picture (on phones and computers) shows it as large as the screen allows, handy for showing a vendor what you're looking for. Tap anywhere to close. A card always opens with the small picture.
- **Totals on the Cards tab only:** the four boxes (Cards owned, Collection value, Cost to finish, Full set value) now show only on the Cards tab. Shopping, Upgrades and Stats open straight onto their own content.
- **Clearer wording, the same words everywhere:**
  - Settings → Phone: the long-press setting reads **Hold a card: eBay sold** (it used to say "Hold: eBay sold"), and its page is titled **Press and hold a card**.
  - Your own collections are called **binders** everywhere (the menu was titled "Your sets").
  - **Price check** everywhere instead of a mix of "refresh" and "price check". Settings → Daily refresh is now **Daily price check**, and the binder's status line says "prices checked every night".
  - **Pictures** instead of a mix of "images" and "pictures".
  - The shopping list's **Bought** button is now **Got it**, the same as in card show mode.
- Stats on phones: "21 before tracking" is now "21 undated", and the gain reads "+$2,614 vs. paid", so neither gets cut off.

## v3.21.3 (October 18, 2026)

- **Type a seller in card show mode:** under Seller on the Got it screen, pick the site or app (Instagram, TikTok, Facebook, X, Whatnot, eBay, Venmo, Cash App, PayPal, a website or a card shop) and type their username. It shows the link it will save so you can check it. Pasting their profile link picks the right site by itself. Sellers you type are remembered for the rest of the day, like scanned ones.
- **Linktree sellers:** a vendor QR code that goes to a Linktree (most do) saves the seller as "Linktree @name", and tapping it opens their page with all their links. Beacons and Stan pages work the same way, and all three are in the seller list.
- Fixed: Venmo, Cash App and PayPal were missing from the seller list when adding a purchase in a card's details.

## v3.21.2 (October 18, 2026)

- **Clear saved copy:** Settings → Server → **Clear saved copy** deletes the copy of the app, binder data and card pictures kept on that phone or computer, then downloads a fresh one. Use it if the app seems stuck on old information. Your binders stay on the server, changes waiting to sync stay on the phone, and it only works while connected so the app always has something to open.

## v3.21.1 (October 18, 2026)

- **Card show mode moved to the ☰ menu:** the top of the menu now switches between **My binders** and **Card show**. Card show mode has the same ☰ button at its top left, so you can switch back either way. The button in the Card shows (calendar) window is gone.

## v3.21 (October 18, 2026)

- **Card show mode:** one list of every card you still need from the binders you're working on, with prices, search by name or number, and sorting by cheapest, priciest or binder. Tap **Got it** to log a buy: the price you paid (it tells you how far over or under the price you are), condition, and where. Where and condition are remembered for the day. Open it from **Card shows → Start card show mode** or the ☰ menu on My binders.
- **Works with no signal:** the list is saved on the phone, and buys made offline wait there and sync after you confirm, like other offline changes. The condition comes along now too.
- **Scan a vendor's QR code:** on the Got it screen, **Scan vendor QR** takes a photo of a vendor's code and adds them as the seller: Venmo, Cash App, PayPal, Instagram, TikTok, Facebook, X, Whatnot, eBay, or any website. Sellers you scan stay on the list for the rest of the day, so the next buy from the same table is one tap. Needs Chrome on Android.
- **Working on:** pick which binders you're collecting right now. Card show mode uses them, and they get a small "Working on" tag on My binders.
- Venmo, Cash App and PayPal are now seller choices when you log any purchase.

## v3.20 (October 18, 2026)

- **Old price warning:** a small clock next to a card's price means the price may be out of date: its newest sale is over 3 months old, or there are no recent sales and TCGplayer's market price is used instead. A note under the cards explains the clock, and the card's details show when it last sold. On old prices the clock takes the place of the up/down arrow.

## v3.19.5 (October 17, 2026)

- **Card shows stay listed through the day after.** A show happening on the day of a weekly check (or running late) is no longer at risk of disappearing. Shows older than yesterday now drop off each day on their own instead of waiting for the next weekly check.
- Today's shows get a **Today** tag, and yesterday's are dimmed with a **Yesterday** tag. The "upcoming" count only counts today and later.

## v3.19.4 (October 16, 2026)

- Fixed privacy mode not hiding the totals at the top of a binder (cards owned, collection value, gain, cost to finish). They showed in outlined boxes instead of being blurred. This broke in a behind-the-scenes cleanup in v3.19.1. A new automatic check now catches it if it ever happens again.

## v3.19.3 (October 16, 2026)

- **Set logos on the home page are now the same size.** Squarer logos, like Neo Revelation's, looked much smaller than wide ones. Empty space around each logo is now trimmed, and every logo gets about the same amount of space: wide ones a little shorter, square ones taller.

## v3.19.2 (October 16, 2026)

- **Version links to GitHub:** in Settings → About, tap the version pill (like v3.19.2 ↗) to open that version's notes on GitHub. Previous versions link to theirs too. Shown only when updates come from GitHub.
- Settings → About → Status no longer lists missed set logo or Pokémon artwork downloads as problems. They're retried by themselves (some sets simply have no logo), the same as card pictures.

## v3.19.1 (October 16, 2026)

- **Status works again:** Settings → About → Status said "Couldn't reach the server" even when everything was fine. A newer part of the page (the dates on recently added cards) had reused the name of the one Status relies on and replaced it. They now have separate names, and the automatic tests catch any repeat of this.
- **Cleanup pass (nothing looks different):** removed leftover code from older designs that nothing used any more: 24 unused style rules (the old sets menu rows, the first cover style and others), an unused page helper, and 4 unused server pieces from an older way of collecting prices. The automatic tests now also catch two page elements sharing an id and two server functions sharing a name, and a new cleanup check lists leftovers after each feature release.

## v3.19 (October 16, 2026)

- **Settings are easier to find.** The menu is now in three labeled groups: This device (Appearance, Privacy mode, Phone), Pricing (Prices, Daily refresh) and Data (Backup and import, Server), with About at the bottom.
- **New Phone page** in Settings. It holds Install the binder as an app (moved from Server) and Long press a card (moved from Appearance), and its menu row shows what a long press opens.
- Appearance now only has looks (theme, the Unlimited label, the celebration, tab icon), and Server only has connection settings. Every setting works the same as before.

## v3.18.2 (October 16, 2026)

- **Press and hold a card to check its price.** On phones, holding a card for half a second gives a short buzz, and lifting your finger opens its eBay sold listings. Works on Cards, Pages (not while arranging) and Find a card. A quick tap still opens the card details. Pick eBay sold, TCGplayer, PriceCharting or Nothing in **Settings → Appearance → Long press a card**.

## v3.18.1 (October 16, 2026)

- On phones, long-pressing a card picture, a Pokémon or a binder cover no longer opens the browser's image menu (copy, save, share). Right-clicking on a computer works as before.

## v3.18 (October 16, 2026)

- **Tab bar at the bottom on phones.** Inside a binder, Cards, Pages, Shopping, Upgrades and Stats now sit in a bar at the bottom of the screen with icons, in easy thumb reach. My binders and computers look the same as before.
- **Pages is roomier.** The money summary (cards owned, value, cost to finish) is hidden on the Pages tab; it's still on the other tabs, and each page still shows what it costs to fill. On phones, the pocket size and order sit side by side, and the page flip arrows stay just above the tab bar, fading in over the binder, so you can flip without scrolling.

## v3.17 (October 16, 2026)

- **Download your whole collection as a spreadsheet.** Settings → Backup and import → **Download spreadsheet** gives one Excel file with an "All binders" tab and a tab for each binder: every card, owned or needed, copies, condition, what you paid, today's price, value, the day you got it, and your notes.
- **Loading placeholders.** While a binder loads, grey card outlines show where the cards will be, instead of a blank space.
- **Try again buttons.** When the server can't be reached, the message now has a **Try again** button: opening a binder, saving a card, searching, loading a set, saving your pages, starting a price refresh and loading spending. Messages also say what to check (the server and Tailscale), and none mention "the container" anymore.
- **Accessibility check.** An automatic audit of every main screen in all five themes now passes. Fixes: each card's picture is its own "open details" button, separate from the Need/Owned button, so screen readers and keyboards don't get a button inside a button; the binder screen is marked as the main content.

## v3.16 (October 16, 2026)

- **Smoother screen changes.** Opening a binder slides it in from the right, and going back to My binders (home button or the phone's back gesture) slides it back. Switching tabs (Cards, Pages, Shopping list...) fades, and card details and other windows rise in gently. If your phone is set to reduce motion, everything switches instantly like before.
- **Number on the app icon.** When the binder is installed as an app on a Windows or Mac computer, its icon shows how many offline changes are waiting to sync. Android doesn't support numbers on web app icons, so phones are unchanged.
- Opening the binder you just left from My binders now also starts on its Cards tab.

## v3.15.5 (October 16, 2026)

- **Card shows on My binders:** the calendar button (local card shows) is now at the top of the home page too, next to privacy and Settings.
- **Binders open on Cards:** opening a binder always starts on its Cards tab, instead of whichever tab you used last (Pages, Shopping list...).
- **No more pull-to-refresh:** pulling down at the top of the page no longer reloads it, so scrolling back to the top is safe. If something looks stuck, use **Settings → Server → Reload the app**. Nothing saved is lost, including changes waiting to sync.
- **Launch screen:** the icon now lines up with Android's own launch screen so it doesn't jump at the hand-over, and the scroll bar no longer flashes on the right edge while it shows.

## v3.15.4 (October 16, 2026)

- **Set logos on My binders.** Each set binder's tile now shows the set's logo (the same one as its inside cover) above the year and card count, instead of the name in plain text. Master sets, your own binders, and any set whose logo isn't available keep the name.

## v3.15.3 (October 16, 2026)

- **Smoother launch screen.** The icon is now the same size and in the same spot as Android's own launch screen, so the hand-over between the two no longer looks like a zoom. It stays up for 1.5 seconds so you can see it, then fades into the home page. The thin scroll bar that showed on its right edge is gone.

## v3.15.2 (October 16, 2026)

- **Launch screen for the installed app.** When you open the binder from your home screen, it shows the app icon (your own, if you set one in Settings) on the theme's background while your binders load, then fades into the home page. It shows for at least a moment and never more than 3 seconds. Opening the binder in a regular browser tab skips it.
- The phone app is marked **Android** in Settings and on the project page. It's made for Chrome on Android and isn't set up for iPhone.

## v3.15.1 (October 16, 2026)

- Pages on big computer screens: the two-page spread was stuck to the left with an empty gap on the right. It's now centered and a little bigger, while still fitting the window's height.

## v3.15 (October 16, 2026)

- **Menu button on My binders:** a menu button at the top left of the home page opens your binders list (the same list as in a binder), without going through Edit.
- **Price check progress on My binders:** while prices are being checked, the home page shows which binder, how far along it is, and a progress bar, just like the top of a binder.
- **Status line stays put:** the green dot and "Saved on the server" now sit under the title on the left on every page, on computers as well as phones. On big screens (like 4K), binder pages use the same width as the home page so nothing shifts when you switch.
- **Backup and import fixed:** the backup buttons were showing a giant binder cover behind them (since v3.10). The same fix also covers the picture button when making a custom card.

## v3.14 (October 16, 2026)

- **Bring back or start fresh:** if you add a binder you removed earlier and its cards are still saved, the binder now asks first instead of quietly bringing them back. **Restore** puts back your cards, what you paid, notes and photos, in the binder's old spot. **Start fresh** begins with an empty binder; a backup of everything is saved first, just in case. Prices and price history are kept either way.
- Backups made before a phone sync or a fresh start now have their own names in the list of backups saved on the server.

## v3.13.1 (October 15, 2026)

- **Big screens (like 4K):** the home page uses more of the width, and all your binders plus **Add a binder** fit in one row.
- **Recently added, no scroll bar on computers:** the 12 newest cards now share the row instead of scrolling. On phones it still swipes, with a fainter scroll bar.

## v3.13 (October 15, 2026)

- **Mark cards owned with no connection:** in the phone app, with no signal you can still tap **Need** to mark a card owned, or add a purchase with the price you paid, where, and the seller. It's saved on the phone and shows right away; the offline line says how many changes are waiting. Other changes (condition, notes, photos, removing cards) wait for a connection and are greyed out while offline.
- **Confirm before syncing:** when the connection comes back, a **Ready to sync** window lists each change in plain words ("Dark Espeon · Neo Destiny: now owned · paid $250 at Card show"), says if it adds another copy of a card you already have, and lets you take any of them out. Nothing is sent until you tap **Sync**. Prices aren't listed; they always update to the newest on their own.
- **Undo last sync:** right after syncing (the Undo button) or later in Settings → Server, takes out exactly the purchases that sync added. A backup is also saved on the server right before every sync.
- Settings → Server shows changes waiting to sync, with **Review & sync**.
- A single missed answer from the server no longer flips the dot to red; it tries again first.

## v3.12 (October 15, 2026)

- **Opens with no connection:** the installed phone app (or Chrome on the https address) keeps a saved copy of every binder, its cards, prices and purchases, and the pictures you've looked at. With no signal, it opens from that copy and the dot turns red with "Offline · showing what's saved on this phone." When the connection is back, the dot turns green and everything refreshes from your server.
  - The saved copy refreshes on its own every few hours while you're connected, and right after you reconnect.
  - Changes still need a connection in this version; marking cards owned offline comes next.

## v3.11 (October 15, 2026)

- **Connection dot:** a small dot next to "Saved on …" (and under "My binders" on the home page) shows whether the binder can reach your server: green when it can, red when it can't. It checks every 30 seconds while the page is open, and when your phone's connection changes.
- **Settings → Server → Connection:** says whether you're connected, when it last checked, and which address you're using, with a **Check connection** button.
- **Install as a phone app:** open the binder by a secure (https) address, like its Tailscale name ending in `.ts.net`, and Chrome offers **Install** (also in Settings → Server → Phone app). It then opens from your home screen, full screen, with its own icon (your tab icon from Settings, or the binder icon). Working offline comes in a later version.
- **Settings → Server → Other addresses:** add a web address you set up yourself (like a port-forwarded name) so the binder answers to it, without changing the container settings.
- The phone's top bar takes on your theme's background color.

## v3.10.4 (October 15, 2026)

- Card details: where the card goes in your binder ("Page 7, front, row 1, pocket 2") is now a button with a page icon and a **›** arrow, instead of underlined text. **›** means it opens another part of the binder (the Pages view); **↗** still means a link that leaves the binder.

## v3.10.3 (October 15, 2026)

- Long binder names fit on phones: a name like "Neo Revelation" shrinks a little to fit beside the buttons, and if it's still too long it goes onto two lines instead of being cut off with "…".
- Home page: the "My binders" title uses your theme's two colors, like the binder names.

## v3.10.2 (October 15, 2026)

- Home page: the Completion switch is gone. The eye (privacy) button already hides the completion rings, along with everything else privacy mode hides.

## v3.10.1 (October 15, 2026)

- Home page on phones: the privacy and Settings buttons sat flush against the top of the screen. They now have the same space above them as on a binder, so they line up when you switch between the two.

## v3.10 (October 15, 2026)

- **Home page.** The binder now opens on a home page instead of a binder's card values. It shows a shelf of your binders, each as a small cover with its cover Pokémon in the set's colors, plus its name, year and card count. Tap one to open it.
- **Completion rings** show how complete each binder is. The privacy button hides them, along with Recently added.
- **Find a card** is at the top of the home page.
- **Recently added** shows the cards you got most recently and which binder they're in; tap one to open it. The server now remembers the day a card first becomes owned (older cards use their purchase dates).
- **Add a binder** is the last spot on the shelf, and **Edit** opens the binder list to reorder, remove or get pictures.
- The menu button at the top of a binder is now a **home button**. The phone's back button goes from a binder back to home. A link to a binder (like /#neo4) still opens it directly.
- **Background jobs can't stop for good:** the part of the binder that runs the nightly price check, the daily backup and cleanup now guards every step. Before, an error in one step (like the card show site changing) stopped all of it until the binder restarted, with no nightly prices or daily backups in the meantime. The nightly price check also runs on its own now, so cleanup and backups keep going while it works.
- **Leftover temporary files are cleaned up:** if the binder is stopped partway through an update test, a restore, a backup or a picture download, the half-finished files are deleted the next time it starts, so they can't quietly fill the drive.
- If restarting after an update ever fails, updates are no longer blocked until the container restarts.
- Settings → About → Status stops checking back every 5 seconds once you close Settings, even if the server couldn't be reached.

## v3.9.7 (October 15, 2026)

- **Privacy mode keeps the binder.** Cards and Pages stay open in privacy mode; only Shopping list, Upgrades and Stats are greyed out. In Pages every card shows in color, with no prices, no "owned" counts (each side just says how many cards) and no "Owned first" order.
- **All in color.** A new button in Pages shows the cards you're missing in color too, so the binder looks full. Tap it again for the greyed-out look. The choice is saved with the binder.

## v3.9.6 (October 15, 2026)

- **Cover fallbacks.** If a Shining Pokémon has no shiny artwork, the cover uses its usual colors. If a Pokémon's artwork can't be downloaded, its pick button shows the card's own art instead, and the card's scene shows sharp behind the logo. A failed artwork download waits an hour before trying again, so the server doesn't keep asking.

## v3.9.5 (October 15, 2026)

- **Cover scene from the card.** The featured card's own painted scene now fills the cover behind the Pokémon, softened so it reads as background (the card's Pokémon would otherwise show twice). The Pokémon stands in front with a soft white glow, and the set logo sits near the bottom with a white sticker outline. The band and corner star are gone. Until the card's picture is on the server, the set's colors and rays of light stand in.

## v3.9.4 (October 15, 2026)

- **Cover Pokémon as a full cutout.** The featured Pokémon is now Ken Sugimori's official artwork, the same style the vintage binders used, so it's a clean cutout that's never cut off at the edges. Shining cards show the Pokémon in its shiny colors (Shining Charizard is black). The artwork is downloaded once and kept on the server. The card-art window and its artist credit are gone.

## v3.9.3 (October 15, 2026)

- **Pages open on the inside cover** on phones, like opening a real binder. Swipe or tap page 1 to go on.

## v3.9.2 (October 15, 2026)

- **Inside cover in the style of the vintage set binders.** The pack look is gone (no crimped edges). The cover now has the set's logo in the corner, rays of light, a band across the middle and one featured Pokémon, like the binders made for each set back then. The Neo sets get their binder colors (Destiny is pink, yellow and orange); other sets take theirs from the logo.
- **Pick the cover Pokémon.** Round buttons in the corner switch between the binder's three hits. Your pick is saved with the binder's pages.

## v3.9.1 (October 15, 2026)

- **Softer inside cover.** The cover's background is now the top card's own artwork, softly blurred, with just a hint of the set's colors, so the art and background blend instead of clashing. The light-burst rays are gone, and the art frames are thinner gold, like the frame around the art on the cards.

## v3.9 (October 15, 2026)

- **Pages: pack-style inside cover.** The inside cover now looks like a booster pack: the set's logo over a burst of light, crimped top and bottom edges, and the pack's colors (the four Neo sets have their own; other sets take theirs from the logo).
- **The set's hits as artwork.** The cover shows the artwork from the binder's three most valuable Pokémon cards, cut from the cards' own pictures, so the art is always period correct. It's credited to the original artists ("Art: ..."), read once per set from the card database and kept on the server.

## v3.8.3 (October 15, 2026)

- **Pages: inside cover art.** The inside cover shows the set's logo (from the same card database as the card pictures), with the set name, year and card count. Master sets show the Pokémon's sprite, and your own binders show their name.
- On phones, a **Cover** button comes first in the page buttons (or swipe back from page 1) to see it.

## v3.8.2 (October 15, 2026)

- **eBay sold searches read like listing titles:** year, set, card name, "Holo" for holo cards, and the number, like `2002 Neo Destiny Dark Ampharos Holo #1/105`. The old searches added `-1st` (meant to hide 1st Edition listings), which made them look odd. This applies to card details and Find a card.

## v3.8.1 (October 15, 2026)

- Pages on phones: the page dropdown (which opened your phone's big full-screen list) is replaced by buttons under the page, one per page. Tap a number to go to that page's front, and tap it again for the back. The arrows still step one side at a time.

## v3.8 (October 15, 2026)

- **Find a card:** open the menu and tap **Find a card** to search every English card and set. Type what's printed on the card (a name, the number at the bottom like `80/111`, or both) and tap **Search**. Nothing is searched while you type.
  - Results come in two groups: **Sets** and **Cards**. Each card shows which of your binders already have it, and whether you own it.
  - Open a set to see all its cards as pictures, with **Find in this set** to jump to a name or number, and a button to add the whole set as a binder.
  - Tap a card for its TCGplayer and eBay sold links, the binders it's in (tap to open it there), and **Add to** any binder.
  - The first search after this update makes the list of every card from every set (about a minute, once), with a progress bar. Newly added cards get their prices in the background a few seconds later.
- **Your own binders:** menu > **Add a binder** > **My own**. Name it (like Favorites or Trade pile) and fill it with cards from any set using Find a card. Prices, owned, purchases, photos, spreadsheets and pages work like any other binder.
  - In the sets menu, tap **Edit**, then the binder's name to rename it.
  - Cards you added (to your own binders, or extra cards in a set or master set binder) have **Remove from this binder** in card details.
- **Pages:** a new view that lays your binder out like a real one, with 4, 9, 12 or 16 pockets a page. Page 1 starts on the right after the inside cover, and each page has a front and a back.
  - Start from an order (set number, rarity, Pokédex number, Pokémon then Trainers and Energy, value, owned first, or order added), then tap **Arrange** to move cards: tap a card, then tap where it goes (or drag it with a mouse). **Add gap before** leaves an empty pocket.
  - Owned cards are in color, missing ones are faded with their price, and each side shows how many you own and what it costs to fill.
  - On a computer you see two pages side by side, like an open binder. On a phone you see one side at a time: swipe or use the arrows.
  - Card details say where each card goes, like "Page 3, front, row 2, pocket 1". Tap it to jump there.
- The "Missing a card?" tile at the end of every binder now has **Find a card** as well as **+ Custom card**.

## v3.7.4 (October 14, 2026)

- **Price check progress in Settings → About:** while a price check runs, Status shows a progress bar with "Checking Neo Destiny: card 16 of 113" and the percent, updating every 2 seconds.
- **Updates wait for a price check instead of failing:** if you install an update while prices are being checked, it shows the check's progress bar and installs as soon as the check finishes. Closing Settings while it waits cancels the update.
- **One big job at a time:** updates, rollbacks and backup restores can't overlap each other or a price check. Before, tapping Install twice (or on two devices) could run two updates at once and leave the saved copy for rolling back unusable. A second tap now says an update is already in progress (and doesn't keep retrying). A restore now waits for a running price check, so the check can't write old prices over the restored ones. The nightly check waits for an update or restore to finish instead of skipping a binder.
- **Stuck connections are let go:** a device that connects and goes quiet (like a phone losing signal mid-load) is dropped after a minute instead of tying up part of the server for good.

## v3.7.3 (October 14, 2026)

- Card details on a computer: the window is as tall as the card picture side and no taller, so there's no big empty space, and it keeps the same size when you switch tabs. The **Prices** tab now shows the recent sales right under the prices (on phones, Recent sales stays its own tab).
- Card details: the store buttons are now eBay sold, PriceCharting, TCGplayer. On a computer they line up as two equal buttons with TCGplayer across the full width below.

## v3.7.2 (October 14, 2026)

- **Reorder your binders:** in the sets menu, tap **Edit**, then drag the ⠿ handle next to a binder to move it up or down (or focus the handle and use the arrow keys). The new order is saved on the server, so it's the same on every device.
- **Get pictures now:** in the sets menu, tap Edit to see how many of each binder's pictures are saved on the server. **Get pictures** downloads the rest right away instead of waiting the hour a new binder waits.

## v3.7.1 (October 14, 2026)

- Binder complete celebration on phones: bigger letters that fill the width, a taller swirl, and the word sits nearer the middle of the screen.
- Tapping to close the celebration no longer flashes the screen blue on phones.

## v3.7 (October 14, 2026)

- **Binder complete celebration:** when you own every card in a binder, Unown swirl around the screen like the vortex in Pokémon 3, then fly into place to spell **CONGRATS** and float gently. Tap anywhere (or press Escape) to close. It closes by itself after about 14 seconds.
  - Settings → Appearance → **Binder complete**: turn it off for this device, or tap **Play** to see it any time.
  - The Unown pictures (from Pokémon Crystal) download once and are kept on the server. If your device asks for less motion, the letters appear in place without the swirl.

## v3.6 (October 14, 2026)

- **Card details, reworked:** on a computer the window is wider, with the card picture, name and links on the left and the details on the right, each side scrolling on its own. On phones the picture, name and links are centered at the top.
  - Three tabs: **Prices**, **Recent sales**, and **My copy** (copies, condition, purchases, notes and photos), so there's much less scrolling. The tabs stay at the top while you scroll.
  - Under the name: "You own this card · LP" or "Still needed". The My copy tab shows how many copies you have. Both hide in privacy mode.
  - Your copy's photo sits next to its button instead of below it.
- Settings: sections no longer get squashed, so About → Status shows every row instead of cutting off the bottom.
- Sets menu: the Pokémon picture next to a master set's name lines up with the name instead of sitting low.
- Fixed a price note that said "no recent sales" when there were sales.

## v3.5 (October 14, 2026)

- **Card pictures load faster and use less space:** the grid uses small pictures, and the full-size scan only loads when you open a card. Pictures download as you look at them instead of all at once.
- **Quick test binders stay light:** a new binder waits an hour before filling in the rest of its pictures, and its first price check waits 2 minutes. If you remove it before then, nothing more is downloaded. A price check also stops if its binder is removed partway through.
- **Faster nightly price check:** it checks every card you own each night, and the cards you still need every 3 days, taking turns. Turn on **Check every card every night** in Settings → Daily refresh to check all of them nightly. The Refresh prices button still checks the whole set you're viewing.
- **Fonts are built in:** the page no longer asks Google for its fonts, so it loads faster and works the same with no internet.
- **Daily backup:** a backup is saved on the server every day, and the last 7 are kept (Settings → Backup → Saved on the server).
- **Status in Settings → About:** last price check, last backup, database size, picture storage, free space, and any problems in the last day.
- **Self-check:** the binder checks itself every 2 minutes and restarts if it stops answering for about 6 minutes.

## v3.4 (October 13, 2026)

- **Undo for removing a binder:** an Undo button shows for 10 seconds after you remove one. Removed binders stay under **Recently removed** (tap Edit in the sets menu) for 30 days, with all their cards, purchases, photos and prices, and can be restored to the same spot. After 30 days they're deleted for good.
- **Summaries line up:** the totals at the top of the page, in the sets menu and in Stats share one tidy box. Labels, numbers and notes sit on the same lines across each row, and the progress bar sits next to the %. On phones the summary takes less room, so cards show sooner.
- On a computer, clicking anywhere outside the sets menu closes it. That click only closes the menu (buttons at the top still work right away).

## v3.3 (October 13, 2026)

- **Smoother drag to reorder in the shopping list:** the row you grab lifts and follows your finger, the other rows slide out of its way, and it settles into place when you let go.
  - Drag near the top or bottom of the screen and the page scrolls by itself. Press Escape to put the row back.
  - Phones give a tiny buzz when the row lifts. The arrow keys still move rows too.

## v3.2.1 (October 13, 2026)

- Sets menu: the progress rings use your theme's two colors, like the progress bar on the page, and the all-binders summary has the same bar. Master sets get the same ring as every other binder, with the Pokémon's picture next to its name.

## v3.2 (October 13, 2026)

- **Tidier sets menu:** each binder is one slim row with a progress ring, cards owned and value, and the binder you're viewing is highlighted. The all-binders summary is smaller.
  - Remove buttons are hidden until you tap **Edit**, so a binder can't be removed by accident (it still asks twice).
  - On phones the menu covers the whole screen, with no strip of the page showing on the right.

## v3.1 (October 13, 2026)

- **New Settings layout:** a short list of sections (Appearance, Prices, Daily refresh, Backup and import, Server, About), each showing its current value. On a phone, tap one to open it full screen and use the back arrow (or your phone's back gesture) to return. On a computer the list stays on the left. On/off switches replace checkboxes, themes are small color chips, and the help text is shorter.
- On phones, card details, Settings, card shows, What's new and Add a card now fill the whole screen.
- **Name your server:** Settings → Server name. Type what you call the computer the binder runs on (like "Attic") and messages use it: "Saved on Attic", "Can't reach Attic". Left empty, they say "the server", so the binder makes sense for anyone running it.

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
