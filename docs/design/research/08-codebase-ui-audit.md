# 08 — Codebase UI audit (what exists today)

Snapshot of the working tree on 2026-10-01. It includes uncommitted edits to `index.html`, `Island.swift`, `evidence.py`, `routes_integrations.py` and `CLAUDE.md`. **Commit a baseline before any parallel work.** Anchors use the form `file:line`.

## 1. Inventory per surface

**Web dashboard: [alibi/web/index.html](../../../alibi/web/index.html)** (2211 lines: CSS 10–719, markup 722–843, JS 845–2208). One page. Body classes `idle`, `live` and `verdict` reorder the sections with CSS `order` (338–352, 476–479).
- Layers: toast `#toast` 723, Setup drawer 731 (tabs Connections / Habits / Your data, 736–762), reel lightbox 767, correction popover `#pop` 774, onboarding overlay `#onb` 776.
- Sections: header (wordmark "Alibi." plus state pill) 782; Today plan blocks 793; week hero 799; composer, chips and convo 801; Now 811; This week (quote, grid, pace rows) 816; Sessions 835.
- Now states (`renderNow` 951): idle (empty); **live** (ring 984, on-task % 987, drift line 989, live actions 1026, sample strip 995, LIVE frame 1060, window bars 1119); **verdict** (`renderVerdict` 1073: pill, count-up %, meter with partial/done ticks, contact sheet, Watch reel / Fix / Go again / Done).
- Toast kinds (1161): `nudge` (solid red), `verdict`, `report`, `info`, `pace`, `recap`, `planned`, plus local `correction`/`started` (`showToast` 1601).
- Sessions row with expanding detail 1291. Week grid 1734. Plan blocks with states planned / now / live / done / partial / slacked / missed / skipped / waiting (1654, 1682). Onboarding steps welcome → habits → schedule → connect → practice (2051–2109).
- Polling: `/api/state` every 1 s, report/sessions/plan every 15 s, health every 120 s (2206–2208).

**Notch island: [native/Island.swift](../../../native/Island.swift)** (1838 lines). `Mode` is collapsed, expanded or alert (216).
- Collapsed (812). It is the notch size when idle. While something is live it adds 46 pt wings (504–506): leading glyph (826) shows nudge badge / red pulse / break cup / state pulse / ✓ / ▶; trailing value (843) shows `24m`, `45s` or `now`. A red `Glow` shows while drifting and a green one while an alert is queued (777–783).
- Expanded, 400 pt (511): header 908; offline card 974; welcome card 1005; up-next card 1021; session card (ring, strip, %) 1110; controls (Break / +10 / Finish with inline confirm) 1152; composer 943; habit chips with ⌘1–9 shortcuts 1061; footer with `TodayRing` 920.
- Alerts (400 pt, verdict 440): `alertView` 1280 handles nudge, pace, recap, report and info. `plannedView` 1325. `syncedView` 1346 is inferred from an `info` alert whose text starts with "Strava:" (328). `verdictView` 1378 has a badge, %, strip, a 5-frame `thumbRow` 1453, and a "stopped early" variant.
- Alert sounds (355): nudge Funk, planned Purr, verdict Glass, else Tink. Auto-dismiss (364): verdict 15 s, synced 6 s, others 10 s. Nudge and planned stay up until settled (334).
- Hover and pin: `track()` at 30 Hz (1675). Hotkey ⌥⌘A (1658).

**iPhone: [ios/AlibiPhone/AlibiPhoneApp.swift](../../../ios/AlibiPhone/AlibiPhoneApp.swift)** (299 lines). It has a single `HomeView` (225): bold 34 pt "Alibi" with a green dot, a status card, a green "Sync now" button and a 7-day stats table. Forced dark. No app icon (`ASSETCATALOG_COMPILER_APPICON_NAME: ""` in [project.yml](../../../ios/project.yml)). No live-session view.

**Server pages: [routes_integrations.py](../../../alibi/routes_integrations.py)** has its own mini CSS kit at 379–401. Fonts are system sans only, with no serif. Pages: `/strava/setup` 157, Strava callback result cards 83, `/phone` 303/339. Images come from [evidence.py](../../../alibi/evidence.py) (contact sheet: NewYork plus Menlo on `#F2F2F2`) and [reel.py](../../../alibi/reel.py) (1280×720, 6 fps, title card 14, frame tag 26).

## 2. Where tokens live

| Token set | Location |
|---|---|
| Web colours, fonts, shadow (light) | `index.html:11–25`; dark mode `26–35`. Fonts come from Google: Newsreader, Inter, JetBrains Mono (9) |
| Web radii | Ad hoc: 999px pills, 12px cards, 10px frame, 14px lightbox, 8/6/4px small. No token |
| Island colours | `Island.swift:196–205` (`palette`, `accent`, `cream #EEEEEE`, `surface #1A1A1A`, `hairline white 9%`, `green/amber/red`) |
| Island type | `rounded()` 552 (SF Rounded for numbers); `.serif` (New York) inline at 882, 910, 982, 1121, 1293… |
| Island shape | `card()` 677 (16 pt continuous); `PillButton` 621 (9 pt radius, 28/32 pt height); chips 10 pt; `NotchShape` corners 6/10 collapsed, 10/24 open (761) |
| iOS | `green`/`ink` at `AlibiPhoneApp.swift:9–10`; everything else inline |
| Server pages | `routes_integrations.py:379–380` (`--acc`, `--ok`, `--err`…) |
| Images | `evidence.py:7–9` (`COLOURS`, `VERDICT_COLOUR`, neutrals); reel reuses them |

Drift in values: web `--off_task #C8362B`, `--faint #8C8C8C`, `--idle-ink #8A5F00`, select-arrow stroke `%23A39E95` (the old warm palette, 256) and confetti `#7FA7D9` (1627) are all outside the CLAUDE.md palette. The island's `absent` is `#8C8C8C` while the web uses `#A6A6A6`. The contact-sheet verdict pill draws **white text on green** (`evidence.py:47`), which breaks the black-on-green rule.

## 3. Current motion

- **Web**: 25 different px font sizes, with 12px used 59 times. Easing is `cubic-bezier(.2,.7,.2,1)` ×12, plus `.2,.75,.2,1` ×2 and `.3,.6,.4,1` ×1. There are no motion tokens.
  - Keyframes: `pulse` 2.4 s (56), `rise` .35 s (77), `pop` .6 s (108), `blink` 1.6/1.2 s (104, 403), `flip` .9 s (326), `cele` 1.1 s (545), `fall` confetti 1.2–2.1 s with 46 pieces (547, 1624), `spin` .8 s (282).
  - Transitions: ring arc 1 s linear (93); bars .8 s (137); drawer .42 s (209); toast .35 s (186); popover .18/.22 s (307); session detail `grid-template-rows` .35 s (175); `countUp` 900 ms cubic-out (1067).
  - `prefers-reduced-motion` turns off **every** animation and transition (719).
- **Island**:
  - Mode changes: spring 0.38/0.86 (789); alert in 0.42/0.78 (354); collapse 0.40/0.85 (382, 1631, 1710); hover open 0.42/0.80 (1701); session or drift change 0.42/0.80 (790–791).
  - Content transition: opacity plus scale 0.96 anchored at the top (799, 806).
  - Small motion: press 0.97 with easeOut 0.12 (616); `Pulse` 1.6 s (587); `Glow` 1.1 s autoreverse (596); `.numericText()` on the countdown and % (847, 1142).
  - There is no reduced-motion check.
- **iOS**: none.

## 4. Signals a mascot can react to

Everything below comes from polling. `/api/state` returns **only the latest alert** (`api.py:149`), so a UI has to diff `alert.id` and session fields between polls. If several alerts can land inside one poll, use `/api/feed`.

| Event | Source | Detect |
|---|---|---|
| Session started / ended | `state.session` | `session.id` goes null → n / n → null |
| Warming up | `session.warming_up` (fewer than 6 samples, `api.py:102`) | flag |
| New sample, on/off task | `session.labels[]`, `recent[-1]`, `recent_on_task`, `last_seen.label` | `labels.length` grows; read the newest label |
| Drifting / phone | `session.drifting {label, since_s, samples}` (2+ non-on-task in a row, `api.py:106`) | non-null; `label==="phone"` |
| Nudge fired | alert `kind:"nudge"`, `label`, `strike` ([nudges.py:84](../../../alibi/nudges.py)); `session.nudges`, `session.strikes` | new alert id, or a count goes up |
| Break / back | `session.on_break {until,left_s}`, `breaks_taken`; feed `source:"you"` `back`/`resume` | non-null ↔ null |
| Verdict | alert `kind:"verdict"` with `verdict`, `ratio`, `ended_early`, `missed` ([cli.py:237](../../../alibi/cli.py), [daemon.py:57](../../../alibi/daemon.py)); `state.recent_verdict` stays for 10 min | new id; done → celebrate, partial → shrug, slacked → sad |
| Streak | `/api/report` `rows[].streak_days`, `streak_today`; verdict text has a streak tail | after a verdict, refetch the report |
| Correction | `POST /api/sessions/{id}/correct` reply; `labels[].corrected_from`; feed `correction` | client-side, on success |
| Plan block now | alert `kind:"planned"` (`calendar_sync.py:654`); `/api/calendar/plan` `next.state==="now"` | either one |
| Strava run | alert `kind:"info"` text `"Strava: …"` (`daemon.py:105`, `integrations.py:108`); Strava claim = `verdict` with no `session_id` (`daemon.py:128`) | prefix match (no real `synced` kind exists) |
| Health synced | **no alert at all**; `/ingest` writes silently | poll `/api/apple-health/status.last_received` / `latest_date` |
| Pace / report / recap | alert kinds `pace`, `report`, `recap` (`daemon.py:86,177,193`) | new id |
| Today tally | `state.today.habits_done/total`, `verdicts{}` | value changes |
| Offline | fetch fails | island `online=false` |

Cheapest improvement: add `mood` plus `event_seq` to `/api/state`, computed server-side. Alternatively emit `notify(kind="synced")` from the Health ingest and from the Strava sync, so all three UIs share one rulebook.

## 5. Mirroring the live session on iPhone

- **What the phone can reach today**: the opt-in phone listener on `0.0.0.0:8766`. It serves only `POST /ingest` and `GET /phone` ([integrations.py:345–382](../../../alibi/integrations.py)) and is gated by `X-Alibi-Secret`, checked with `hmac.compare_digest` (308).
- **Addresses**: `addresses()` (313) returns Tailscale HTTPS (only when `tailscale serve` proxies 8766), Wi-Fi IP, `.local` and the Tailscale IP. All of them are already baked into `Generated/AlibiConfig.plist` by [build_install.sh](../../../ios/build_install.sh).
- **What it can't reach**: the main API stays on `127.0.0.1:8765` with a `TrustedHostMiddleware` (`api.py:33–35`). It is unreachable from the phone, and it should stay that way.
- **New endpoints needed** (small; add them inside `phone_app()`, with the same secret check):
  - `GET /phone/state`: a trimmed `/api/state`, i.e. `session` without `labels[].frame_url`, `alert`, `today` and `recent_verdict` (summary/verdict/ratio), plus `plan.next`.
  - Optional `POST /phone/say {text}`, which calls `cli.say`, so the phone can start, break or end.
  - Optional `GET /phone/frame?ts=` if thumbnails are wanted.
- **On the phone**: derive the base URL by stripping `/ingest` from the stored good endpoint and poll every 2–3 s while the app is in the foreground. A Live Activity would need a widget extension target, and updates while the app is backgrounded are unreliable without APNs. **Treat it as a stretch goal.** An in-app "Now" card is the safe demo.

## 6. Build and verify

- Toolchain: Swift 6.2.4 (arm64-apple-macosx26.0); Xcode 26.3 (17C529); xcodegen at `/opt/homebrew/bin`.
- Simulators (iOS 26.2): iPhone 17 Pro / 17 Pro Max / Air / 17 / 16e / SE Narrow Test, plus iPads.
- **Island**: `bash scripts/build_native.sh` runs `swiftc -O native/Island.swift` and rebuilds `Alibi.app`. `./alibi.sh up` rebuilds only if `native/Island.swift` is newer than the app (`alibi.sh:24`).
- **Snapshot**: `bin/alibi-island --snapshot DIR [--state FILE.json] [--prefix P]` writes 640×460 @2x PNGs. Fixture extras: `_plan`, `_needs_setup`, `_alerts[{name,alert}]`, `_only`, `_confirm_finish` (1725–1731). Verified today with the daemon down: 6 renders, notch 185×32. Text fields render as a yellow placeholder.
- **Button test**: `bin/alibi-island --act "Back to it"` (1801).
- **Tests**: `./alibi.sh test` runs `tests/run_all.sh`, 17 Python DoD tests (P0–P11, robustness, integrations, calendar, onboarding, journey), each in a temp data dir. Only `test_p2.py:18` touches the UI (`GET /` → 200), so extracting CSS/JS is safe.
- **iOS device**: `bash ios/build_install.sh` needs Alibi running with phone sync on, then runs xcodegen, `xcodebuild`, and `devicectl install` + launch.
- **iOS simulator** (no signing):
  ```
  cd ios && xcodegen generate && xcodebuild -project AlibiPhone.xcodeproj -scheme AlibiPhone -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath build build
  xcrun simctl boot "iPhone 17 Pro"; xcrun simctl install booted build/Build/Products/Debug-iphonesimulator/AlibiPhone.app
  xcrun simctl launch booted app.theultras.alibi; xcrun simctl io booted screenshot shot.png
  ```
- **Multi-file Swift gotcha (verified)**: `swiftc Island.swift Mascot.swift` fails with "statements are not allowed at the top level". Move `Island.swift:1820–1838` into `native/main.swift`, then compile `native/main.swift native/Island.swift native/Mascot.swift …`, and update the freshness check in `alibi.sh:24`. iOS has no such issue: xcodegen picks up every file in `ios/AlibiPhone/`.

## 7. The 10 biggest weaknesses

1. **No character.** Nothing reacts emotionally; a verdict is a pill plus confetti. There is no mascot slot on any surface.
2. **Type sprawl.** 25 px sizes on the web and 15 pt sizes on the island (8–19). Mono uppercase eyebrows at 12px appear 59 times and read as a dev console, not Claude-calm.
3. **The iPhone app is a utility.** It uses bold system type with no serif and no tokens, has no icon, no light mode and no live session. In a demo it looks like a debug tool.
4. **The page jumps.** The `live` and `verdict` modes reorder whole sections and shrink the composer (345–352), and nothing animates the move.
5. **The nudge toast is a red slab.** Solid `--warn-ink` with white text, staying 60 s (192, 1168). It is alarming rather than calm.
6. **Off-palette leftovers.** Listed in §2. `--faint #8C8C8C` on `#F2F2F2` is about 3:1, which fails AA for text, and it is used for meta text.
7. **Motion is ad hoc.** Three cubic-beziers, more than 10 durations, island springs from 0.35 to 0.42, no shared tokens. Reduced motion kills even state feedback, and the island ignores it entirely.
8. **Mixed icon language.** Emoji (📷💻🏃❤️⬛📅) on the web next to SF Symbols on the island.
9. **Information density.** The week hero has 3 stats plus a gauge plus a bar. The verdict panel has 7 elements. The session row has 6 columns.
10. **Events are fragile.** UIs poll 1 Hz with the full payload (all labels) and see only the latest alert. Health sync is invisible, and "synced" is guessed from text. A mascot built on this flickers or misses beats unless state is diffed carefully.

## 8. Merge-conflict hotspots and how to split the work

The riskiest files are `alibi/web/index.html` (one file, three languages, every feature), `native/Island.swift` (tokens, model, every view and the entry point in one file), and `CLAUDE.md`, whose design section was rewritten during this session, so agents may load conflicting rules (sans-only vs serif). `alibi/api.py` (`/api/state`) and `alibi/integrations.py` (`phone_app`) are the backend touch-points.

**Step 0** (one agent, about 20 min, then commit; nothing else starts before it):
- Split the web CSS into `alibi/web/css/{tokens,base,components,sections}.css` and the JS into `alibi/web/js/{core,now,week,sessions,setup,onboarding}.js`. Load them as plain `<script src="/web/js/…">` so globals keep working; they are already served by `api.py:394–395`.
- Split Swift into `native/{main,Island,Theme,Mascot}.swift` and update `build_native.sh` and `alibi.sh`.
- Freeze the token names.

**Then run in parallel, one owner per file:**

| Agent | Owns |
|---|---|
| A — tokens and type | `tokens.css`, `Theme.swift`, iOS `Theme.swift`, `evidence.py` `COLOURS` |
| B — mascot | `mascot.js` + `mascot.svg`, `Mascot.swift` shared by the island and iOS (copied file), a `mood` field in `api.py` |
| C — dashboard sections | `now.js`, `week.js`, `sessions.js`, `sections.css` |
| D — island views | `Island.swift` only |
| E — iPhone | `ios/AlibiPhone/*.swift` plus `/phone/state` in `integrations.py` |
| F — demo | `demo/shotlist.md`, fixtures for `--snapshot` |

Gate: `./alibi.sh test` stays green, and the island snapshot PNGs are re-rendered per PR.
