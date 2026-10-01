# Alibi redesign: implementation plan (P15–P19)

Thursday 1 October 2026. Applications close on 2 October. Written at 17:20 BST for agents to execute from 18:30.

- **Design source of truth:** `docs/design/system/project/` (README, Motion, Mascot, `tokens.json`). It is published as the Design System artifact <https://claude.ai/artifact/VWhz2UkEU9ir1RMNZwAyYD>, and the screens canvas is <https://claude.ai/artifact/Q6LdSrcfPBjfASofdchzJi>.
- **Research behind it:** `docs/design/RESEARCH.md`, as corrected by the user decisions in §1.
- **Timeboxes and gates:** this file.

Where the three disagree, apply them in this order: **§1 user decisions > `system/project/*` > this file > RESEARCH.md > research/**.

Demo plan: [`DEMO.md`](DEMO.md). Tools used by every DoD below: [`tools/`](tools/) (`render.py`, `imgdiff.py`, `lint_design.py`).

---

## 0. How to use this plan

1. **Find your lane** in §4 (ownership) and §5 (Gantt). Edit only the files your lane owns. To change anyone else's file, post the request to the integrator (lane L0) with the exact diff.
2. **Run work packages in order.** Each package has a DoD command and its expected output. "Code written" is not done. A package is done when the command prints the expected output **and** you have looked at the render or screenshot with the Read tool.
3. **Timeboxes are hard.** When a box expires, take that package's "If behind" path, say so in your lane's status line (§5.1), and move on.
4. **Commit by pathspec** after every package (§9). Never `git add -A` or `git commit -a`. Another session commits to this repo all evening.
5. **Keep the camera off** unless a physical session is running. Lab work uses the mock witness and fixture video (§3.3).

---

## 1. Frozen decisions (do not re-open)

| # | Decision | Consequence for code |
|---|---|---|
| 1 | **All-sans precision.** No serif anywhere: no Source Serif, New York, Newsreader, Georgia or italic. | Web uses `--font-sans` (`-apple-system, BlinkMacSystemFont, "SF Pro Text", "Onest", system-ui, sans-serif`), `--font-rounded` for big numerals and `--font-mono` for keycaps and IDs only. Apple uses `Alibi.Fonts.*`. Pinch's voice is the `voice` style (20/1.45, w500), in the same family. Every number uses `tabular-nums` / `.monospacedDigit()`. |
| 2 | **Dark first.** `bg #000`, `surface-1 #1A1A1A`, `surface-2 #262626`. Light is a complete second theme. | Web: `<html data-theme>` takes `dark` or `light`. With no attribute, the page is dark unless the OS prefers light. The island is always dark. The iPhone app stays dark this round; making light work on the phone is a COULD and needs ask A6. |
| 3 | **Pinch** is an original green detective lobster with a magnifying lens. It is never called Nemo-anything and uses no NVIDIA marks. | The lens tells the truth. It glows only while the camera is sampling, shows an empty ring when the camera is off, and rests at Pinch's side when there is no session (Mascot.md "Identity"). |
| 4 | **iPhone** is a full companion with Today, Week and Health, plus a **Live Activity**. | Uses lanes L4 and L5. The iPhone 14 on the desk has **no Dynamic Island**, so Dynamic Island shots come from the iPhone 17 Pro simulator (§11, risk R3). |
| 5 | **Colour.** `#76B900` is the accent, at ≤5% of the chrome (Pinch is exempt). Text on green is always `#000`. Status colours always come with a shape. There are no gradients except the single celebration `bloom`. | Lint rules `raw-hex-*`, `gradient`, `retired-colour` and `uppercase` in `tools/lint_design.py` enforce this. |

**Frozen type scale, token names, the `window.Alibi` component contract and the `AlibiPinch` engine contract.** These are exactly as written in `system/project/README.md` and `tokens.json`. Copy names from there and never invent new ones. When a token you need does not exist, use the nearest existing token and leave a `lint-ok: needs token <name>` comment. L0 collects these comments at 20:10.

---

## 2. What exists and what lands

**Code today** (anchors from research/08, re-checked at 17:20):
- `alibi/web/index.html` has 2211 lines: `<style>` 10–720, markup 722–843, `<script>` 845–2209. Google Fonts load Newsreader, Inter and JetBrains Mono.
- `native/Island.swift` has 1838 lines. Top-level entry code sits at 1820–1838. Its private `extension Color { init(hex:) }` at 207–215 **collides** with `Theme.swift`'s `init(hex:alpha:)`.
- `ios/AlibiPhone/Views/` contains Home, Onboarding, Permissions and Theme. `HomeView` is the app root. It is named in `AlibiPhoneApp.swift`, which the other session owns, so we **keep the type name `HomeView`** as our root.
- `HomeView.swift:61,65` write the `row("phone", "app", …)` contract rows. `tests/test_ios_contract.py` checks for them, so **keep them**.
- Phone listener: `alibi/integrations.py` `phone_app()` on `:8766` serves `POST /ingest` and `GET /api/phone/session`. Both use `X-Alibi-Secret`.
- `tests/run_all.sh` runs 20 tests.

**Design assets in `docs/design/`.** These are landing about 18:20; the Wave 0 gate checks for them.

| Asset | Path | Becomes |
|---|---|---|
| CSS tokens (`:root` dark, light block, type classes `.t-*`, springs) | `tokens/tokens.css` | `alibi/web/css/tokens.css` |
| Swift tokens (`enum Alibi { Palette, Fonts, Space, Radius, Motion }`, `Color(hex:)`) | `tokens/Theme.swift` | `native/Theme.swift` (shared with iOS through `project.yml` sources) |
| Pinch web engine (`window.AlibiPinch`) and pose lab | `pinch/pinch.js`, `pinch/lab.html` | `alibi/web/js/pinch.js` |
| Pinch SwiftUI rig | `pinch/Pinch.swift`, `pinch/PinchData.swift` | `native/Pinch.swift`, `native/PinchData.swift` (shared with iOS) |
| Component kit (`window.Alibi`, `bundle.css`) | `system/project/**` | reference only. The dashboard does not load React; the shell lane ports the CSS recipes with the `al-` class prefix. |
| Screens canvas | `canvas/project/**` | reference only: layouts for every surface and state |

---

## 3. Shared environment

### 3.1 Toolchain (verified 17:20)
- **Toolchain:** Swift 6.2, Xcode 26.3, xcodegen 2.46, Node 24, ffmpeg. `python3` has Playwright and Pillow; `.venv/bin/python` is the app's environment.
- **Mac:** a MacBook with a built-in notch display at 3024×1964 Retina, plus an external 2560×1440 display. The island picks the screen that has a notch.
- **Phone:** **iPhone 14 on iOS 26.3.1**, paired and named "Harrish". It has no Dynamic Island. The simulators are iPhone 17 Pro and others on iOS 26.2.

### 3.2 Commands every lane uses

```bash
# Render (prints "wrote OUT"; console errors go to stderr — stderr must be empty)
python3 docs/design/tools/render.py URL_OR_FILE OUT.png --w 1280 --h 900 --wait 1500 [--dark|--light] [--reduced-motion] [--full] [--eval "js"]
# Pixel diff (exit 0 when changed-pixel ratio <= --max-ratio)
python3 docs/design/tools/imgdiff.py BEFORE.png AFTER.png --max-ratio 0.002 --out DIFF.png
# Design lint (last line "lint_design OK (0 findings, N files)")
python3 docs/design/tools/lint_design.py --web | --swift | --paths FILES…
# Swift type-checks
swiftc -typecheck -target arm64-apple-macos14.0 native/main.swift native/Island.swift native/Theme.swift native/Pinch.swift native/PinchData.swift
swiftc -typecheck -sdk "$(xcrun --sdk iphonesimulator --show-sdk-path)" -target arm64-apple-ios17.0-simulator native/Theme.swift native/Pinch.swift native/PinchData.swift
```

At 17:20 the lint reports **223 findings in 6 files**: 58 `serif-generic`, 35 `raw-hex-css`, 18 `uppercase`, 15 `swift-serif`, and others. This is the worklist for lanes L1–L4. Every lane's DoD ends at 0 for the files it owns.

### 3.3 The lab server
Wave 0 starts the lab server, and any lane may restart it. It runs an API-only process with no daemon loop and no camera, on its own port and its own copy of the data, so it never touches the other session's daemon on `:8765`:

```bash
LAB=/tmp/alibi-lab; [ -d $LAB ] || cp -R data/demo $LAB
ALIBI_DATA_DIR=$LAB API_PORT=8775 .venv/bin/python -c "from alibi import api; import time; api.serve_in_thread(); time.sleep(1e9)" > /tmp/alibi-lab.log 2>&1 &
curl -s 127.0.0.1:8775/api/state | python3 -c "import json,sys; print(sorted(json.load(sys.stdin)))"
# → ['alert', 'daemon', 'habits', 'now', 'recent_verdict', 'session', 'status_text', 'text_model', 'today', 'witness', 'witness_label']
```

(Smoke-tested at 17:30: the dashboard renders from it in dark mode.) After L6 ships `docs/design/demo/stage.py`, full scripted sessions run with `stage.py SCENARIO --port 8775 --data /tmp/alibi-lab` (§6, L6).

**Never run `./alibi.sh up`, `down` or `demo` during Waves 0–2.** `down` runs `pkill -f alibi.daemon` and kills the other session's daemon. Island lanes use `--snapshot` and never launch a second live island over the notch.

### 3.4 iOS build lock and derived data
Xcode projects are generated into the shared, gitignored `ios/AlibiPhone.xcodeproj`. Serialise every `xcodegen` and `xcodebuild` call with `lockf`, and keep derived data per lane:

```bash
cd ios && lockf -k /tmp/alibi-ios.lock sh -c 'xcodegen generate --quiet && xcodebuild -project AlibiPhone.xcodeproj -scheme AlibiPhone \
  -destination "platform=iOS Simulator,name=iPhone 17 Pro" -derivedDataPath /tmp/alibi-<lane>-sim CODE_SIGNING_ALLOWED=NO build' | tail -1
# → ** BUILD SUCCEEDED **
```

---

## 4. Ownership (exclusive; worktree-safe)

| Lane | Agent | Owns: may create and edit | Reads only |
|---|---|---|---|
| **L0** | Integrator / lead | Runs Wave 0. Afterwards: the `CLAUDE.md` "Design system" section, `alibi.sh` (freshness check only), `scripts/build_native.sh` (`alibi-island` compile line only), `native/main.swift`, `ios/project.yml` (the 3 Wave 0 source lines), the §5.1 status board, tags | everything |
| **L1** | Web shell | `alibi/web/index.html`, `alibi/web/css/{tokens,app,base,components,sections}.css`, `alibi/web/js/app.js`, `alibi/web/js/icons.js`, `alibi/web/signals.html`, `alibi/web/fixtures/**` | `js/pinch.js`, `js/moments.js` |
| **L2** | Web moments + Pinch on the web | `alibi/web/js/moments.js`, `alibi/web/js/pinch-wire.js`, `alibi/web/js/confetti.js`, `alibi/web/js/pinch.js` (installed copy), `alibi/web/css/moments.css` | `app.js`, `tokens.css` |
| **L3** | Island | `native/Island.swift`, `native/Theme.swift`, `native/Pinch.swift`, `native/PinchData.swift`, `docs/design/fixtures/island/**` | `main.swift` |
| **L4** | iPhone app | `ios/AlibiPhone/Views/**` except `Views/Live/**`; `ios/AlibiPhone/Assets.xcassets/**` (once ask A5 is granted) | `native/Theme.swift`, `native/Pinch*.swift`, `Views/Live/*` |
| **L5** | Live Activity | `ios/AlibiLive/**` (new), `ios/AlibiPhone/Views/Live/**`, `ios/project.yml` (new `AlibiLive` block plus 2 additive lines in `AlibiPhone`: the dependency and `NSSupportsLiveActivities`) | `Views/Mirror/*`, `native/Theme.swift`, `native/Pinch*.swift` |
| **L6** | Pinch rulebook + demo staging | `alibi/pinch.py` (new), `tests/test_pinch.py` (new), **one line each** in `alibi/api.py` `state()` and `alibi/integrations.py` `phone_session()` (§9.3), `docs/design/demo/**`, `docs/design/fixtures/state/**` | everything |
| **V1–V3** | Wave 2 reviewers | nothing; they report findings only | everything |

**Cross-lane contracts**, created as stubs in Wave 0 so every lane compiles from 18:50:
- **`window.AlibiMoments`** (L2 implements; L1 calls it from `app.js`). See Appendix D.
- **`PhoneSession`** decodable model in `ios/AlibiPhone/Views/Mirror/PhoneSession.swift` (L4 owns it; L5 reads it). See Appendix C.
- **`LiveActivityController.shared.sync(_:)`** and **`LiveActivityButton`** in `Views/Live/` (L5 implements; L4 calls them from Today).
- **The `pinch` field** `{mood, event, seq, ref}` on `/api/state` and `/api/phone/session` (L6 implements; L2, L3 and L4 consume it). See Appendix B.

**Worktrees.**
- **Default: one checkout.** Lanes run in the main checkout. File ownership is disjoint and commits are made by pathspec.
- **Using worktrees.** If you run a lane in a `git worktree` (`.claude/worktrees/<lane>` is gitignored), branch from the `p16-design` tag. Copy `data/demo` to your own `ALIBI_DATA_DIR`. L0 merges with `git merge --no-ff design/<lane>` at 20:50. Ownership is disjoint, so the merge is conflict-free by construction.
- **Build products.** `bin/` and `Alibi.app/` are per-checkout. Only L3 runs `scripts/build_native.sh` in the main checkout.

---

## 5. Timeline (BST)

| Lane | 18:30–18:50 | 18:50–19:30 | 19:30–20:10 | 20:10–20:50 | 20:50–21:05 | 21:05–21:30 | 21:30–22:45 |
|---|---|---|---|---|---|---|---|
| **L0** | **Wave 0** (serial, everyone else waits) | Status board; answers cross-lane requests; **19:30 checkpoint** | **20:10 checkpoint**; reruns the full gate every 20 min | Feature-freeze prep; merges worktrees | Runs gate G2 (§7.1) | Final gate; tags p17–p20 | Operates `stage.py` for capture (DEMO.md) |
| **L1** web shell | — | S1 foundation | S2 IA + hero strip | S3 week, sessions and setup on tokens; S4 signals.html | — | Fixes P0/P1 | — |
| **L2** web moments | — | M1 Pinch wiring | M2 verdict reveal, M3 nudge card | M4 composer FLIP + polaroid (SHOULD), M5 fix a moment | — | Fixes | — |
| **L3** island | — | I1 tokens, type, springs, reduced motion | I2 Pinch rungs, I3 bloom | I4 nudge alert, I5 verdict alert; I6 wings/peek (SHOULD) | — | Fixes | Rebuild for capture |
| **L4** iPhone | — | P1 tab shell + theme | P2 Today (live mirror) | P3 Week + Health, P4 haptics + icon | — | Fixes | Install on device |
| **L5** Live Activity | — | A0 signing probe (**go/no-go 19:20**) | A1 widget views | A2 start/update/end, A3 device + simulator run | — | Fixes | Simulator Dynamic Island take |
| **L6** rules + staging | — | K1 starter fixtures (by 19:05), K2 `pinch.py` + test | K3 call sites, K4 `stage.py` | K5 real fixtures, K6 demo cards | — | Fixes | Title and end cards |
| **V1–V3** | — | — | — | — | **Adversarial review** | Verify fixes | — |
| **User** | Reads DEMO.md | — | Approves the 19:30 screenshots | — | — | Pre-flight (DEMO.md §6) | **Records 21:45–22:15; edits 22:15–22:45** |

### 5.1 Status board
L0 keeps the status board in this file under this heading, one line per lane, updated at every checkpoint. Line format: `L3 19:30 — I1 done (commit abc123), I2 in progress, on time`.

### 5.2 Checkpoints
- **19:30:**
  - Every lane has its first package's DoD green.
  - L5 reports its A0 result: either the extension signs for the device, or it falls back to simulator only (see A0).
  - L0 posts four screenshots for the user: dashboard dark, dashboard light, island expanded, iPhone Today.
- **20:10:**
  - All MUST packages are in progress or done.
  - Any lane more than 20 min behind drops its SHOULD/COULD packages (§9).
  - L6's real fixtures replace the starter ones.
- **20:50: feature freeze.** After this, only fixes from Wave 2 findings.
- **21:30: tags cut.** Recording starts with whatever is tagged.

---

## 6. Wave 0: foundations (serial, one agent, 18:30–18:50, box 20 min)

Nothing else starts until `p16-design` is tagged. The goal is to put the assets at their production paths and open the multi-file seams, **with no visual change**.

### Gate (2 min)
```bash
git log --oneline -3                                   # the other session's checkpoint commit is on top (or they said "go")
git status --porcelain -- scripts/build_native.sh ios/project.yml alibi.sh CLAUDE.md alibi/web native/Island.swift
# → empty: nobody has uncommitted edits in the files Wave 0 touches
ls docs/design/tokens/tokens.css docs/design/tokens/Theme.swift docs/design/pinch/pinch.js docs/design/pinch/Pinch.swift docs/design/pinch/PinchData.swift
# → all five exist
```
If a file is dirty, ask the other session to commit it and wait at most 10 min. If they don't, do the web steps first and the Swift and iOS steps last.

If a design asset is missing:
- **`pinch.js` or the Pinch Swift files:** continue. Create `native/Pinch.swift` as a placeholder `PinchView` that draws a 1:1.15 green capsule with two dot eyes, using the same public init as the contract. L3 swaps in the real rig on arrival.
- **Either tokens file:** stop and ask.

### Steps
1. **Baseline renders (3 min).** Start the lab server (§3.3), then:
   ```bash
   mkdir -p /tmp/p15 && for t in dark light; do python3 docs/design/tools/render.py http://127.0.0.1:8775/ /tmp/p15/before-$t.png --w 1280 --h 1800 --wait 2000 --$t; done
   ```
2. **Install assets (2 min).** Copy them to production paths:
   - `docs/design/tokens/tokens.css` to `alibi/web/css/tokens.css`
   - `docs/design/pinch/pinch.js` to `alibi/web/js/pinch.js`
   - `docs/design/tokens/Theme.swift` to `native/Theme.swift`
   - `docs/design/pinch/Pinch.swift` and `PinchData.swift` to `native/`

   Do not link `tokens.css` or `pinch.js` from `index.html` yet. The legacy `:root` uses the same names (`--bg`, `--ink`, `--accent` and others), so linking now would change the page. L1 links them in S1.
3. **Split the web page (5 min).** No logic changes:
   - Move the inside of `<style>` (lines 11–719) verbatim to `alibi/web/css/app.css`, and replace the block with `<link rel="stylesheet" href="/web/css/app.css">`. Keep the Google Fonts `<link>` for now.
   - Move the inside of `<script>` (lines 846–2208) verbatim to `alibi/web/js/app.js`, and replace the block with:
     ```html
     <script src="/web/js/moments.js"></script>
     <script src="/web/js/app.js"></script>
     ```
     Both are classic scripts at the same position, so top-level `const`s stay global.
   - Create the `alibi/web/js/moments.js` stub from Appendix D. It holds no-ops, and `nudge()` returns `false`.
   - Insert the six hook calls into `app.js` (Appendix D, "call sites"). With the stubs, these do nothing.
4. **Swift seams (5 min).**
   - Move `Island.swift` lines 1820–1838 (from `let args = CommandLine.arguments` to the end) into a new `native/main.swift`.
   - Delete `Island.swift`'s `extension Color { init(hex: UInt32) … }` (207–215). Theme.swift supplies `Color(hex:alpha:)`.
   - Check collisions:
     ```bash
     rg -n "^(enum|struct|final class|class|func|let|var|extension) (Pinch|Pose|Mood|Clip|PinchView|Alibi)\b" native/Island.swift
     ```
     This must print nothing. If it prints anything, rename the Island symbol, never the asset's.
   - In `scripts/build_native.sh`, replace `swiftc -O native/Island.swift -o bin/alibi-island` with:
     ```bash
     swiftc -O native/main.swift native/Island.swift native/Theme.swift native/Pinch.swift native/PinchData.swift -o bin/alibi-island
     ```
   - In `alibi.sh` `up`, replace `! [ native/Island.swift -nt Alibi.app/Contents/MacOS/Alibi ]` with:
     ```bash
     [ -z "$(find native -name '*.swift' ! -name witness.swift ! -name sense.swift ! -name calendar.swift -newer Alibi.app/Contents/MacOS/Alibi -print -quit)" ]
     ```
5. **iOS seams (4 min).**
   - In `ios/project.yml`, under `targets.AlibiPhone.sources`, append exactly three lines and nothing else:
     ```yaml
     - path: ../native/Theme.swift
     - path: ../native/Pinch.swift
     - path: ../native/PinchData.swift
     ```
   - Create the stubs `ios/AlibiPhone/Views/Mirror/PhoneSession.swift` (Appendix C model) and `ios/AlibiPhone/Views/Live/LiveActivityController.swift` (with `import SwiftUI`):
     ```swift
     @MainActor final class LiveActivityController {
         static let shared = LiveActivityController()
         func sync(_ s: PhoneSession?) {}
     }
     struct LiveActivityButton: View { var body: some View { EmptyView() } }
     ```
6. **Rewrite the `CLAUDE.md` "Design system" section (2 min).** Replace everything from `## Design system` to the end of the island sizing bullet with Appendix A, verbatim. Touch nothing else in `CLAUDE.md`.
7. **Verify, then commit (4 min)** using the DoD below and §9.

### DoD (all must hold)
```bash
for t in dark light; do python3 docs/design/tools/render.py http://127.0.0.1:8775/ /tmp/p15/after-$t.png --w 1280 --h 1800 --wait 2000 --$t; \
  python3 docs/design/tools/imgdiff.py /tmp/p15/before-$t.png /tmp/p15/after-$t.png --max-ratio 0.002 --out /tmp/p15/diff-$t.png; done
# → "identical", or "diff ratio=0.000xx bbox=(…)" where the bbox is only the "as of HH:MM" clock line; exit 0; render stderr empty
bash scripts/build_native.sh | tail -1                 # → Built Alibi.app (double-click it, or ./alibi.sh up)
mkdir -p /tmp/p15/island && bin/alibi-island --snapshot /tmp/p15/island
# → notch 185.0x32.0 hasNotch=true online=… renders=6   (6 PNGs; Read island_expanded.png and island_alert.png: unchanged look)
swiftc -typecheck -sdk "$(xcrun --sdk iphonesimulator --show-sdk-path)" -target arm64-apple-ios17.0-simulator \
  native/Theme.swift native/Pinch.swift native/PinchData.swift ios/AlibiPhone/Views/Theme.swift && echo ios-shared-ok   # → ios-shared-ok
(cd ios && lockf -k /tmp/alibi-ios.lock sh -c 'xcodegen generate --quiet && xcodebuild -project AlibiPhone.xcodeproj -scheme AlibiPhone -destination "platform=iOS Simulator,name=iPhone 17 Pro" -derivedDataPath /tmp/alibi-l0-sim CODE_SIGNING_ALLOWED=NO build' | tail -1)
# → ** BUILD SUCCEEDED **
./alibi.sh test                                        # → 20 rows, no FAILED, exit 0
rg -n "Newsreader|New York|serif" CLAUDE.md            # → only the "No serif anywhere" rule line
```
Then commit and tag (§9): `p16 design foundations: tokens, Pinch rig, web/Swift seams`, tag `p16-design`. Announce on the status board. Wave 1 starts.

**If behind** at 18:50:
- Skip the light-mode diff.
- Skip the iOS simulator build (L4 runs it as P1's first step).
- **Never skip** the build, the snapshot or `./alibi.sh test`.

---

## 7. Wave 1: lanes (18:50–20:50)

Package format: **Goal · Files · Steps · DoD → expected · Box · If behind · Delivers**.

### L1: web shell

**S1 Foundation on tokens (18:50–19:30, box 40)**
- **Goal:** the dashboard is dark-first, all-sans, on frozen tokens, with nothing yet re-arranged.
- **Files:** `index.html`, `css/app.css`, new `css/base.css` and `css/components.css`, `js/app.js`, new `js/icons.js`.
- **Steps:**
  1. **Head and fonts.** In `<head>`, link `/web/css/tokens.css` first, then `base.css`, `components.css`, `app.css` and `moments.css`. Delete the Newsreader/Inter/JetBrains `<link>` (tokens.css `@import`s Onest). Add a pre-paint theme script: read `localStorage` `alibi.theme`, wrap the read in try/catch, and set `document.documentElement.dataset.theme` only when the user picked one.
  2. **Retire the legacy `:root` blocks** in `app.css`. Replace them with a compatibility block so existing rules keep working:
     ```css
     --paper:var(--surface-1); --muted:var(--ink-2); --faint:var(--ink-3); --rule:var(--hairline-strong); --rule-2:var(--hairline);
     --on_task:var(--on-task); --off_task:var(--off-task); --on_task-ink:var(--on-task-ink); --idle-ink:var(--partial-ink);
     --phone-ink:var(--warn-ink); --serif:var(--font-sans); --sans:var(--font-sans); --mono:var(--font-mono); --shadow:var(--shadow-float);
     ```
     In `app.js`, change `cvar`/`vvar` to map labels: `on_task`→`on-task`, `off_task`→`off-task`, `partial`→`partly` only for the verdict alias.
  3. **Typography.**
     - Body is 16px. Replace every `font-family:var(--serif)` heading and quote with the `.t-h1`, `.t-h2`, `.t-h3` or `.t-voice` classes, or their declarations.
     - Delete the 59 uppercase mono eyebrows. They become `.t-label`, in sentence case.
     - Add `font-variant-numeric: tabular-nums` to every number.
     - Use `text-wrap: balance` on headings and `pretty` on prose.
  4. **Colour fixes** (RESEARCH §2.2): retire `#C8362B`, the `%23A39E95` select arrow and the `#7FA7D9` confetti. The off-task state gets its 45° hatch, using `background-image` with `var(--off-task)` stripes and no gradient tokens.
  5. **Motion.**
     - Replace the blanket reduced-motion kill (old line 719) with the "fewer, gentler" block from `system/project/Motion.md` "Reduced motion".
     - Meters change from `width` to `transform: scaleX()`.
     - Every `cubic-bezier(…)` becomes `var(--ease-out)`, `var(--ease-drawer)` or a `--spring-*` token.
  6. **Icons.** Emoji (📷💻🏃❤️⬛📅) become the inline SVG `icons.js` set: 1.5px stroke on a 24 grid with `currentColor`, using the names in the component contract. Expose it as `window.AlibiIcons.svg(name, size)`.
  7. **Theme toggle** in the Setup drawer: System, Dark, Light.
- **DoD:**
  ```bash
  python3 docs/design/tools/lint_design.py --paths alibi/web/index.html alibi/web/css/app.css alibi/web/css/base.css alibi/web/css/components.css alibi/web/js/app.js alibi/web/js/icons.js
  # → lint_design OK (0 findings, 6 files)
  for t in dark light; do python3 docs/design/tools/render.py http://127.0.0.1:8775/ /tmp/p16/s1-$t.png --w 1280 --h 1800 --wait 2000 --$t; done   # stderr empty
  python3 docs/design/tools/render.py http://127.0.0.1:8775/ /tmp/p16/s1-rm.png --w 1280 --h 1800 --dark --reduced-motion   # stderr empty
  ./alibi.sh test | rg -c FAILED                          # → 0
  ```
  Then Read both theme renders and check:
  - no serif or italic text anywhere
  - the green CTA has black text
  - light mode is a complete theme, not an inversion
  - no uppercase labels
- **Box:** 40 min.
- **If behind:** keep the compatibility block and leave the hatch and icons for S3. Lint may then show `emoji` findings only.
- **Delivers:** "Precision, not ornament". Every later frame of the demo depends on this.

**S2 Information architecture and hero strip (19:30–20:10, box 40)**
- **Goal:** the 5-second story from RESEARCH §2.8, against the canvas layouts.
- **Files:** `index.html`, new `css/sections.css`, `js/app.js`.
- **Steps:**
  1. **Single column.** `max-width: 880px`, 24px card gaps, sections 48–72px apart, prose capped at 62ch.
  2. **Hero strip** (≤120px):
     - A `#pinch-hero` mount (64px; L2 mounts Pinch there).
     - The honesty line in `.t-voice`: "You claimed 2h 10m. I saw 1h 52m." Build it from `/api/report`. When it is missing, use the copy "Nothing claimed yet. What are you about to do?"
     - The streak pill: claw icon, "6 days · 1 freeze left", built from `rows[].streak_days`.
  3. **Now/composer card** that swaps in place:
     - **Idle:** the composer (56px tall, `radius-lg`, placeholder "What are you about to do?", 36px round green send button with a black arrow) plus 3 chips with `Kbd` hints.
     - **Live:** ring timer card with `#pinch-now` (96px), the on-task stat, the last 6 samples and the drift line.
  4. **Order below the Now card:** latest verdict (contact sheet as hero proof), then today's timeline with a 2px green now-line, then this week, then sessions. Setup stays in the drawer.
  5. **Replace CSS `order` reordering** (old 338–352) with a stable DOM order. The page shape no longer jumps between idle, live and verdict; only the Now card swaps.
  6. **`?stage=NAME` mode.** When present, `pollState` reads `/web/fixtures/NAME.json` instead of `/api/state`. Copy `docs/design/fixtures/state/*.json` to `alibi/web/fixtures/` whenever L6 updates them. The demo depends on this.
- **DoD:**
  ```bash
  for s in idle live_focused verdict_done; do python3 docs/design/tools/render.py "http://127.0.0.1:8775/?stage=$s" /tmp/p16/s2-$s.png --w 1280 --h 1600 --wait 2500 --dark; done   # stderr empty
  ```
  Read the renders:
  - The hero strip shows a number and a sentence above the fold at 1280×800.
  - Idle shows the composer, live shows the ring, and the verdict shows the contact sheet first.
- **Box:** 40 min.
- **If behind:** keep the old section order and only add the hero strip and stage mode.
- **Delivers:** signature moment 4, "Claimed vs seen + proof".

**S3 Week, sessions and setup on tokens; S4 signals.html (20:10–20:50, box 40)**
- **Week:** a 7-dot grid with shape-coded dots and paired claimed/seen bars. Use `scaleX` bars, no chart library. The report quote is set in `.t-voice`.
- **Sessions:** collapse 6 columns to 3: habit and time, verdict pill (`✓ Done` · `◐ Partly` · `✕ Slacked`, glyph plus word), and seen/claimed.
- **Setup drawer:** dark surfaces, sentence-case tabs, and a "Quiet lobster" toggle (COULD) that sets `localStorage alibi.quiet=1`, which L2 reads.
- **S4:** restyle `signals.html` on `tokens.css` once the other session's checkpoint has landed. Change no logic.
- **DoD:**
  ```bash
  python3 docs/design/tools/lint_design.py --web          # → lint_design OK (0 findings, N files)
  python3 docs/design/tools/render.py "http://127.0.0.1:8775/?stage=idle" /tmp/p16/s3.png --w 1280 --h 2600 --full --dark   # stderr empty
  ```
- **If behind:** do S4 last, or drop it (it is a COULD).

### L2: web moments and Pinch on the web

**M1 Pinch wiring (18:50–19:30, box 40)**
- **Files:** `js/pinch-wire.js`, `js/moments.js` (replacing the stub), `css/moments.css`.
- **Steps:**
  1. Mount `AlibiPinch.mount(#pinch-hero, {size:64})` and `#pinch-now` (96). Use `theme:'auto'`, which follows `data-theme`.
  2. Implement `AlibiMoments.state(s)`:
     - `s.pinch.mood` becomes `inst.set(mood)`.
     - When `s.pinch.seq` exceeds the last seq seen on this page, call `inst.play(s.pinch.event)`. Use `{force:true}` for verdict clips and for the `nudge` that chains after `sideeye`.
     - **On first load, record seq without playing**, so a reload never replays an old event.
  3. Client-only moods:
     - The composer's focus or input sets `listening`; blur restores the server mood.
     - The report section in view (IntersectionObserver) sets `reading`.
     - `document.hidden` pauses the engine.
     - Freeze on `idle` after 2 min with no input.
  4. Honour the Mascot.md caps: one clip per 90s (enforced by the engine), at most 3 side-eyes per session, and none during focused work. When `localStorage alibi.quiet` is set, skip clips.
  5. **`PinchLine`:** a 20px avatar plus a `.t-voice` line. It is used by the nudge card and the verdict.
- **DoD:**
  ```bash
  python3 docs/design/tools/render.py "http://127.0.0.1:8775/?stage=live_focused" /tmp/p16/m1.png --w 1280 --h 900 --wait 2500 --dark \
    --eval "AlibiPinch && document.querySelectorAll('#pinch-hero svg, #pinch-now svg').length"
  # → eval -> 2   (stderr empty; Read: Pinch focused in the Now card, idle-sized in the hero)
  ```
- **If behind:** mount only `#pinch-now` and drive it by seq; skip the client-only moods.
- **Delivers:** "One system". The same mascot appears on every surface.

**M2 Verdict reveal (19:30–20:00, box 30). MUST: signature moment 1.**
- `AlibiMoments.verdict(rv, cardEl, {animate})` follows Motion.md §1 exactly:
  - 0 ms: the card rises 12px on `--spring-smooth`.
  - 150 ms: the pill blurs in on `--spring-bouncy`.
  - 300 ms: the % counts up over 900 ms in rAF with tnum, and the meter fills with `scaleX` over the same 900 ms.
  - 1200 ms: Pinch plays `celebrate`, `partial` or `supportive`, and `confetti.js` fires a burst of 28 claw, spark and dot particles in a 60° cone from Pinch's claws (done only).
- **Bloom and big celebration** only on the first win and on streak days 3, 7, 14 and 21, then every 7th day.
- **Interaction:** a click anywhere skips to the end state. `?moment=verdict` replays the reveal on load (the demo needs this).
- **Reduced motion:** fade only, no count-up and no confetti, with Pinch on its still final pose.
- **DoD:**
  ```bash
  for v in done partial slacked; do python3 docs/design/tools/render.py "http://127.0.0.1:8775/?stage=verdict_$v&moment=verdict" /tmp/p16/m2-$v.png --w 1280 --h 1000 --wait 2800 --dark; done
  python3 docs/design/tools/render.py "http://127.0.0.1:8775/?stage=verdict_done&moment=verdict" /tmp/p16/m2-mid.png --w 1280 --h 1000 --wait 700 --dark
  ```
  Read the renders and check:
  - mid-render: the % is between 0 and the final value and the meter is partly filled
  - done: confetti is visible
  - partial: shrug, no confetti
  - slacked: Pinch is supportive and green, with no red slab
- **If behind:** skip confetti; keep the count-up and Pinch.

**M3 Nudge card (20:00–20:10, box 10). MUST: signature moment 2, web side.**
- `AlibiMoments.nudge(alert, s)` returns `true` and renders a neutral `surface-2` card with `PinchLine` (sideeye → nudge).
- Only the noun is in `--warn-ink`. Find it with `/\b(phone|YouTube|…)\b/` on `alert.label_text`, falling back to `alert.label`.
- Buttons are relabelled from the server actions: "I'm back"→"Back to it", "It's on task"→"This counts", "Snooze 5m"→"Quiet 5 min". The posted payload stays the same.
- The red slab toast is never shown for nudges again.
- **Pinch's line is composed on the client.** The server text (`nudges.py` `LINES`: "Still drawing? Your phone's been out for 3 min.") is not in Pinch's voice. Build the line from `alert.habit_label`, `alert.label` and `session.drifting.since_s`:
  - camera labels: "You said drawing. I've seen your phone for 3 minutes."
  - window labels: "You said C++. That's been YouTube for 4 minutes."
  - otherwise: fall back to `alert.text`. Ask A11 aligns the server text, so the macOS banner and the reel match.
- **DoD:** `render.py "…/?stage=nudge_phone"` must show the card with the noun in red ink and no solid red fill.

**M4 Composer → session FLIP + polaroid develop (20:10–20:35, box 25). SHOULD: signature moments 5 and 8.**
- **`sessionStart(fromEl, toEl)`:**
  - Send presses the button to 0.97.
  - The typed text blurs 2px and fades over 150 ms.
  - FLIP the composer rect into the ring card on `--spring-snappy`.
- **`sample(label, imgEl, dotEl)`:** the new frame does `translateY(6→0)` with opacity over 260 ms, then develops over 1200 ms (`grayscale(1) brightness(1.5) blur(6px)` → `none`), then the dot pops on `--spring-bouncy`.
- **If behind:** cut it. The page still swaps in place, because S2 has no jump.

**M5 Fix a moment (20:35–20:50, box 15). SHOULD: signature moment 6.**
- **`correction(sid, ts, newLabel, dotEl, reply)`:**
  - The popover scales 0.96→1 from the clicked dot. Fix the `transform-origin` so it is computed from the dot rect.
  - The dot recolours on `--spring-micro` and the % ticks.
  - Pinch plays `surprise` with `{force:false}`.
  - `PinchLine`: "Fair. I've changed that one."
- **DoD:** run the correction from Playwright against the lab server:
  ```bash
  --eval "document.querySelector('.strip .dot')?.click(); 1"
  ```
  Read the result: the popover is anchored to the dot.

### L3: island (`native/Island.swift` plus the shared Swift assets)

Visual check without screen recording: `bin/alibi-island --snapshot DIR --state FIXTURE.json`.

L6 ships `docs/design/fixtures/state/*.json` by 19:05 (starter) and 20:15 (real). L3 adds island extras in `docs/design/fixtures/island/all.json`: `_alerts` for `nudge_phone`, `nudge_window`, `verdict_done`, `verdict_partial`, `verdict_slacked`, `break`, and `planned`.

**I1 Tokens, type, springs, reduced motion (18:50–19:20, box 30)**
- **Colours:** replace `palette`, `accent`, `cream`, `surface`, `hairline`, `green`, `amber` and `red` (Island.swift 196–205) with `Alibi.Palette.dark.*`. Absent becomes `absent` (`#A6A6A6`).
- **Type:** every `.serif` goes to `Alibi.Fonts.islandTitle` or `islandVoice`; there are 15 today. The 11pt floor fixes the old line 603; the lint rule `font-floor` flags offenders.
- **Springs:** collapse the 6 ad-hoc springs to `Alibi.Motion.island` (open), `.smooth` (every close) and `.snappy` (inner content and wings). Alert drops use `.bouncy`.
- **Reduced motion:** `@Environment(\.accessibilityReduceMotion)`, routed through `Alibi.Motion.adaptive(…)`.
- **Widths:** expanded 400, nudge 400, verdict 440 (CLAUDE.md as rewritten in Wave 0).
- **DoD:**
  ```bash
  python3 docs/design/tools/lint_design.py --paths native/Island.swift native/main.swift   # → lint_design OK (0 findings, 2 files)
  bash scripts/build_native.sh | tail -1                                                 # → Built Alibi.app (…)
  bin/alibi-island --snapshot /tmp/p17/i1 --state docs/design/fixtures/state/live_focused.json   # → … renders=N (N ≥ 6)
  ```
  Read the expanded and alert PNGs: all text is sans, there is no text below 11pt, and the cards are concentric (radius 28 outer, 16 inner).

**I2 Pinch at every rung (19:20–19:40, box 20)**
- **Wings:** a 16pt still silhouette, tinted by status. It shows `focused`, a side-eye still while `session.drifting`, or `sleepy` on a break. No loop ever runs in the wings.
- **Expanded header:** 28pt. It is `listening` while the composer is focused, `focused` while live, and `idle` otherwise. The lens glows only while camera sampling is live (`session.modality` is physical or hybrid).
- **Data:** decode `StateResp.pinch: PinchState?` (optional, so an older daemon still decodes). Diff `seq` exactly as the web does (Appendix B).
- Stop all animation when the island is collapsed, or after 2 min idle.
- **DoD:** the snapshot shows Pinch in the expanded header and in the wing, and the iOS typecheck of `native/Pinch*.swift` still passes (§3.2). L3 owns the shared rig, so **any change to `Pinch.swift` must keep it SwiftUI-only.**

**I3 Bloom choreography (19:40–20:10, box 30). MUST: signature moment 3.**
- **Open:** the shape moves first on `.island` and the shadow fades in over 180 ms. At +70 ms the content arrives with the `Reveal` modifier (opacity, blur 8→0, scale 0.96 from the top) over 260 ms. Tiers then follow 30 ms apart, capped at 3.
- **Close:** content leaves over 120 ms with an ease-out exit (`Alibi.Motion.exit`), then the shape collapses on `.smooth`. It never bounces into the hardware notch.
- **⌥⌘A** animates the shape only, at 0.3 s, with no blur.
- **No shadow** when collapsed. When open, use `black .5 r6 y2` plus `black .35 r24 y12`.
- **Hover rules are unchanged.** Dwell is 0.35 s. Leave margins are 32/48pt plus 0.8 s. A click pins the island.
- **Keep `FirstClickHostingView`.**
- **DoD:**
  - The snapshots still render.
  - Code review: the open and close paths use only the Theme springs. Check with `rg -n "withAnimation\(|\.animation\(" native/Island.swift`; every hit must reference `Alibi.Motion`.
  - Run `bin/alibi-island --act "I'm back"` against the lab server with a nudge fixture. It must print `pressed “I'm back” on nudge: …`.

**I4 Nudge alert (20:10–20:30, box 20). MUST: signature moment 2.**
- **Size and Pinch:** 400 × about 150. A 56pt Pinch plays `sideeye` then `nudge`.
- **Copy:** the `islandVoice` line, with only the noun in `warnInk`. Compose it on the client exactly as M3 does, with the same fallback to `alert.text`.
- **Buttons:** relabelled (as in M3) but matched on the server label, so `--act` keeps working.
- **Motion:** the drop uses `.bouncy`. A phone nudge then gets one 360 ms shake (`0,-6,5,-3,2,0`); soft drift gets none.
- **Sound:** none. Funk is retired for nudges, because nudges stay silent (Mascot.md).
- **DoD:**
  ```bash
  bin/alibi-island --snapshot /tmp/p17/i4 --state docs/design/fixtures/island/all.json
  ```
  `island_nudge_phone.png` shows the 56pt Pinch, the red noun only, and three buttons with the primary green carrying black text.

**I5 Verdict alert (20:30–20:50, box 20). MUST: signature moment 1, island side.**
- **Layout:** 440 × about 190. A 64pt Pinch plays its verdict clip. The pill is `✓ Done` in black text on green, `◐ Partly` on amber or `✕ Slacked` as warn ink on a wash. Below it, a 3-frame strip, then [See proof] and [Something's wrong?].
- **Done only:** a radial `bloom` behind Pinch for the duration of the clip. `RadialGradient` is allowed on that line with `// bloom`.
- **Sound:** Glass is retired. The Mac stays silent by default.
- **DoD:** the snapshot shows the three verdict PNGs. Read them: Pinch stays green on slacked, and there is no red slab.

**I6 Wings slide and hover peek (SHOULD, only if I5 is green by 20:40)**
- Wings slide x ±24 → 0 on `.snappy`, with the right wing following 60 ms later.
- The value uses `.contentTransition(.numericText(countsDown: true))`.
- Peek grows the island by +12w/+4h, and Pinch tilts 8° toward the pointer.

**I7 `--stage FILE` live player (COULD, for demo insurance)**
- Shows the real window with a fixture state, with no polling, and steps through `[{at_ms, state}]`. Only when everything else is tagged.

### L4: iPhone app (`ios/AlibiPhone/Views/**`)

**P1 Tab shell and theme (18:50–19:20, box 30)**
- **`HomeView`** becomes the root `TabView` with Today, Week and Health. It uses the system tab bar's default glass and no custom glass.
- **The current `HomeView` content moves to `HealthView`** (streams, Screen Time, Home, Sync now, privacy note). **Keep its `scenePhase` `row("phone","app",…)` logic and the onboarding sheet on the root.**
- **`Views/Theme.swift`** keeps its public names (`Palette`, `Tone`, `Card`, `SectionLabel`, `PrimaryButtonStyle`, `SecondaryButtonStyle`, `Dot`). `AlibiPhoneApp.swift` uses `Palette.accent`. Re-implement them on `Alibi.Palette.dark` and `Alibi.Radius`:
  - `Card`: 20pt padding, `radius-md`.
  - `SectionLabel`: sentence case, no `.uppercased()`.
  - Buttons: 10pt radius, black on green.
- **DoD:**
  - Run the §3.4 simulator build. It must print `** BUILD SUCCEEDED **`.
  - Take a screenshot:
    ```bash
    xcrun simctl boot "iPhone 17 Pro"; xcrun simctl install booted /tmp/alibi-l4-sim/Build/Products/Debug-iphonesimulator/AlibiPhone.app
    xcrun simctl launch booted app.theultras.alibi; xcrun simctl io booted screenshot /tmp/p18/p1.png
    ```
  - Run `.venv/bin/python tests/test_ios_contract.py | tail -1`. It must print its OK line.

**P2 Today: the live mirror (19:20–20:10, box 50). MUST.**
- **`Views/Mirror/MirrorClient.swift`** (`@MainActor ObservableObject`):
  - While `scenePhase == .active`, poll `GET /api/phone/session` every 3 s with `X-Alibi-Secret: Config.key`.
  - Get the URL from `Config.sibling(of:path:)` on each `Config.endpoints` entry in turn, and remember the first one that works.
  - Decode leniently into `PhoneSession`. Every field is optional, so today's flat reply also decodes.
  - Publish `session`, `online` and `lastOK`.
  - On every update, call `LiveActivityController.shared.sync(session)`.
- **`TodayView`, live:**
  - 160pt Pinch, mood from `pinch` plus seq diffing as on the web.
  - The ring is `ProgressView(timerInterval:)`, styled with the hero timer `Text(timerInterval: start...end, countsDown: true)` in Rounded 56 semibold with `.monospacedDigit()`.
  - The on-task % uses `ios-stat`. The last label is shown as a shape-coded dot plus a word.
  - Pinch's line in `ios-headline` medium.
  - `LiveActivityButton()` ("Show on Lock Screen").
- **`TodayView`, idle:**
  - The honesty line built from `today`, `plan_next` ("Drawing at 19:00"), the streak and the recent verdict card with its Pinch clip.
  - A "Start on Mac" hint showing ⌥⌘A. There is no remote start in this round.
- **`TodayView`, offline:** "Can't reach your Mac. Same Wi-Fi or Tailscale?" plus a Retry button.
- **Haptics:**
  - `.sensoryFeedback(.success)` when a verdict of done arrives.
  - `.warning` when the nudge count rises.
  - `.selection` on taps.
  - Nothing on partial or slacked.
- **DoD:** the simulator build succeeds. Then run L6's lab session with `stage.py done --port 8765 --phone` **or** use the 8775 lab with a matching key. The phone listener is a different port, so see the K4 `--phone` note and risk R4.

  Take a simulator screenshot during a live session. Read it and check:
  - Pinch is 160pt
  - the timer ticks (take two screenshots 2 s apart and compare them with `imgdiff`; the ratio must be greater than 0)
  - there is no clipped text at the default Dynamic Type size, nor at `xcrun simctl ui booted content_size extra-extra-large`
- **If behind:** use a static ring and drop the verdict card from idle.

**P3 Week and Health (20:10–20:35, box 25)**
- **Week:** 7 shape-coded dots and Swift Charts `BarMark` pairs (claimed vs seen) from `PhoneSession.week`. That field depends on ask A3. **If absent,** show the streak, the 7-day Health activity from `Snapshot.shared.days` and a footnote saying the week view needs the Mac update.
- **Health:** the existing content on tokens, plus "Synced 2 min ago" from `SyncEngine.lastSync`. After a successful manual sync, Pinch plays `connected` locally once.
- **DoD:** the simulator build and 2 screenshots, Read.

**P4 Haptics audit and app icon (20:35–20:50, box 15)**
- **Icon:**
  - Render Pinch at 1024 on `#000`:
    ```bash
    python3 docs/design/tools/render.py docs/design/demo/cards/icon.html /tmp/icon.png --w 1024 --h 1024 --scale 1
    ```
    `icon.html` comes from L6 K6 and uses `AlibiPinch.svg`.
  - Place it as the single-size `AppIcon` in `ios/AlibiPhone/Assets.xcassets`, and set `ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon`. Both steps need ask A5.
  - **If A5 is not granted,** skip the icon. It only shows in the Home Screen shot.
- **DoD:** the simulator Home Screen screenshot shows the icon.

### L5: Live Activity

**A0 Signing probe (18:50–19:20, box 30). Decide go or no-go at 19:20.**
1. Add to `ios/project.yml` the `AlibiLive` target block, plus 2 additive lines in `AlibiPhone`:
   - `- target: AlibiLive` under its dependencies
   - `NSSupportsLiveActivities: true` under its `info.properties`

   ```yaml
   AlibiLive:
     type: app-extension
     platform: iOS
     sources:
       - path: AlibiLive
       - path: AlibiPhone/Views/Live/AlibiLiveAttributes.swift
       - path: ../native/Theme.swift
       - path: ../native/Pinch.swift
       - path: ../native/PinchData.swift
     info:
       path: AlibiLive/Info.plist
       properties:
         CFBundleDisplayName: Alibi
         NSExtension: {NSExtensionPointIdentifier: com.apple.widgetkit-extension}
     settings: {base: {PRODUCT_BUNDLE_IDENTIFIER: app.theultras.alibi.live, GENERATE_INFOPLIST_FILE: NO}}
     dependencies: [{sdk: WidgetKit.framework}, {sdk: SwiftUI.framework}, {sdk: ActivityKit.framework}]
   ```

2. Create a minimal `ios/AlibiLive/AlibiLive.swift`: a `@main WidgetBundle` with one `ActivityConfiguration` that shows `Text(habit)`.
3. Create `Views/Live/AlibiLiveAttributes.swift` from Appendix C.
4. Device build. The phone must be connected and unlocked, and this step does not install anything:
   ```bash
   cd ios && lockf -k /tmp/alibi-ios.lock sh -c 'xcodegen generate --quiet && xcodebuild -project AlibiPhone.xcodeproj -scheme AlibiPhone \
     -destination generic/platform=iOS -derivedDataPath /tmp/alibi-l5-dev -allowProvisioningUpdates build' | tail -1
   ls /tmp/alibi-l5-dev/Build/Products/Debug-iphoneos/AlibiPhone.app/PlugIns
   ```
- **DoD:** the build prints `** BUILD SUCCEEDED **`, and the `PlugIns` listing includes `AlibiLive.appex`. `tests/test_ios_contract.py` still passes.
- **No-go path** (provisioning fails, for example from App ID limits on the team):
  - Keep the target, and build for the **simulator only** with `CODE_SIGNING_ALLOWED=NO`.
  - Record the Lock Screen and the Dynamic Island from the iPhone 17 Pro simulator.
  - Tell L0, which removes the "Lock Screen on your phone" shot from DEMO.md and uses the simulator take instead.
  - If the simulator build also fails by 19:45, **cut the lane**: revert the `project.yml` block in one commit, and the agent joins L4.

**A1 Widget views (19:20–20:00, box 40)**
Lay out per research/05 §B and `system/project/Motion.md` §7, with fonts from `Alibi.Fonts.la*`, all sans.

| Region | Content |
|---|---|
| Lock Screen | `.activityBackgroundTint(.black)`, 14pt padding, about 96pt tall. Row 1: 32pt Pinch (still pose per status), "Drawing", and the timer right-aligned (`Text(timerInterval:countsDown:)`, Rounded 34, monospaced digits). Row 2: a 6pt on-task bar. Row 3: "On task 92% · last seen 18:04" in `ink2`. |
| Compact leading | 20pt Pinch silhouette |
| Compact trailing | timer at `laCompact` in a **fixed 40pt frame**, `accentInk` colour. While drifting, it shows the phone glyph in `warnInk` instead. |
| Minimal | a `ProgressView(timerInterval:)` ring with a 10pt head inside |
| Expanded | leading: 44pt Pinch plus the habit. Trailing: the timer at `laExpandedTrailing`. Bottom: the bar plus the drift line. Uses `.keylineTint(accent)`. |
| End state | the verdict word with its glyph (`✓ Done` in accent ink, `◐ Partly`, `✕ Slacked`), `dismissalPolicy: .after(.now + 1800)` |

- Check `isLuminanceReduced` and skip any motion when it is set. The system ignores `withAnimation` anyway.
- **DoD:** the simulator build succeeds. Add a SwiftUI `#Preview(as: .content, using: AlibiLiveAttributes.preview) { AlibiLiveWidget() } contentStates: {…}`. Then run the app in the simulator with the A2 button, and take screenshots of the Lock Screen (`xcrun simctl io booted screenshot`, after `Cmd-L` in the simulator) and of the Home Screen with the Dynamic Island compact view.

**A2 Controller (20:00–20:20, box 20)**
- `LiveActivityController.sync(_ s: PhoneSession?)`:
  - **Session live with no activity, and the app active:** call `Activity.request(attributes:content: .init(state:, staleDate: endsAt))`.
  - **Changed:** call `update`. Pass an `AlertConfiguration` (silent) only for verdicts.
  - **Ended:** call `end(…, dismissalPolicy: .after(.now+1800))` with the verdict state.
- **Throttle:** at most one update every 15 s, except for status changes.
- `LiveActivityButton`:
  - Visible when a session is live, Live Activities are enabled and none is running.
  - Copy: "Show on Lock Screen".
  - Status line: "On your Lock Screen until 18:25".
- **No APNs.** Mid-session updates land only while the app is open. Don't promise drift alerts on the phone.

**A3 Device and simulator run (20:20–20:50, box 30)**
- **Device:** run `bash ios/build_install.sh`. It needs the main Alibi running with phone sync on, so do it at 21:05–21:30 if the other session's daemon is up now, or else in the pre-flight. Start a session on the Mac, open the app, tap "Show on Lock Screen", then lock the phone.
- **Simulator:** start a lab session and capture a Dynamic Island screenshot plus a 10 s `xcrun simctl io booted recordVideo --codec=h264 /tmp/p19/di.mp4`.
- **DoD:**
  - The device shows the Lock Screen activity with the timer ticking. The human checks it and confirms on the status board.
  - The simulator screenshot shows Pinch in the compact leading slot, and the timer frame does not bloat.

### L6: Pinch rulebook and demo staging

**K1 Starter fixtures (18:50–19:05, box 15)**
- Write `docs/design/demo/make_fixtures.py`. It reads `127.0.0.1:8775/api/state` and the newest session from `/api/sessions?limit=1`, then writes `docs/design/fixtures/state/{idle,live_focused,live_drifting,break,nudge_phone,nudge_window,verdict_done,verdict_partial,verdict_slacked,report}.json`.
- It splices the session into `session` or `recent_verdict` and `alert` (Appendix B kinds), sets `now` consistently, and adds a hand-set `pinch` block.
- **DoD:** `python3 docs/design/demo/make_fixtures.py` must print `wrote 10 fixtures`. Running `bin/alibi-island --snapshot /tmp/x --state docs/design/fixtures/state/verdict_done.json` must decode without printing `state decode failed`.

**K2 `alibi/pinch.py` and `tests/test_pinch.py` (19:05–19:35, box 30)**
- `alibi/pinch.py` is pure stdlib with no I/O. It implements Appendix B: `pinch_state(state, prev) -> {mood, event, seq, ref}`, plus `current(state)`, a thread-safe wrapper that holds `prev` in the module, and `last()`.
- `tests/test_pinch.py` follows the house style: a plain script with `check()` and a last line on pass. It covers:
  - every mood rule and every event mapping
  - seq stability across repeated polls of the same alert
  - seq increments on a new alert id
  - the 3-side-eye cap
  - a first call with `prev=None`
  - a malformed state (`{}`) that returns idle without raising
- **DoD:** `.venv/bin/python tests/test_pinch.py | tail -1` must print `test_pinch OK (16 cases)`.

**K3 Call sites (19:35–19:45, box 10)**
Follow the §9.3 protocol for shared files.
- In `api.py` `state()`, build the dict, then set `out["pinch"] = pinch.current(out)` before returning it. This is one statement plus the import.
- In `integrations.py` `phone_session()`, add `"pinch"`. The value is `pinch.last()` when it is fresh (≤5 s old); otherwise compute it with `pinch.current(api.state(None))` using a local import. **If the other session has already added a `pinch` slot, fill it rather than adding a second one.**
- **DoD:**
  - `curl -s 127.0.0.1:8775/api/state | python3 -c "import json,sys; print(json.load(sys.stdin)['pinch'])"` must print `{'mood': 'idle', 'event': …, 'seq': …, 'ref': …}`.
  - `./alibi.sh test | rg -c FAILED` must print `0`.

**K4 `docs/design/demo/stage.py` (19:45–20:15, box 30)**
This is the deterministic session driver for lab and demo. It is our copy of the `scripts/demo.py` pattern, so we do not edit their file.
- **Usage:**
  ```
  .venv/bin/python docs/design/demo/stage.py SCENARIO [--port 8775] [--data /tmp/alibi-lab] [--every 10] [--say TEXT]
                                             [--live] [--phone] [--island] [--capture DIR]
  SCENARIO  done     on_task 60 s · phone 40 s · on_task 80 s   (3 min; nudge ≈ 1:30; verdict done ≈ 78%)
            partial  on_task 50 s · phone 60 s · on_task 10 s   (2 min; nudge; verdict partial ≈ 50%)
            slacked  on_task 20 s · phone 70 s · absent 30 s    (2 min; nudge; verdict slacked ≈ 17%)
            break    on_task 40 s, then says "break 1", then on_task 60 s
            serve    API and daemon with no session (lab dashboard / island target)
  ```
- **How it runs:**
  - It starts `python -m alibi.daemon` with the following environment. The mock witness reads the colour-coded fixture frames.
    - `ALIBI_DATA_DIR`, `API_PORT=--port`
    - `SAMPLE_EVERY_S=--every`, `NOTIFY=print`, so there are no macOS banners over the island
    - `VISION_BACKEND=mock` and `CAMERA_SOURCE=<tests/make_fixtures.video(...)>`
  - Then it `POST`s `/api/say` and prints one line per transition: `0:42 drifting phone`, `1:31 [nudge] You said drawing…`, `3:00 verdict done 78%`.
- **Flags:**
  - `--live` drops the fixture and the mock, so the camera and witness come from `.env`. It prints cues as `scripts/demo.py` does. The camera is released on exit.
  - `--phone` copies `phone_secret` from `data/secrets.json` into the stage data dir's secret store and sets `phone_sync_enabled`, so the installed iPhone app (baked with the main key and port 8766) can read the session.
  - `--island` launches `bin/alibi-island` with `ALIBI_API` set. Use it only when the real Alibi.app is not running.
  - `--capture DIR` saves `/api/state` at each transition (this feeds K5).
  - Ctrl-C kills the process group and prints `Stage stopped. Camera off.`
- **DoD:** `.venv/bin/python docs/design/demo/stage.py done --port 8775 --data /tmp/alibi-stage --every 5` exits by itself in about 100 s with a last line of `verdict done 7x%`. (This is a 5 s cadence dry run with `--say "draw for 2 minutes"`; the scenario's timings scale with `--every`.)

**K5 Real fixtures (20:15–20:30, box 15)**
- Run `stage.py done|partial|slacked|break --capture docs/design/fixtures/state/`. This overwrites the starter fixtures with real payloads, including `pinch`.
- Tell L1, which copies them to `alibi/web/fixtures/`.

**K6 Demo cards and Pinch stills (20:30–20:50, box 20)**
- Create `docs/design/demo/cards/{title,end,icon}.html`. They use `pinch.js` and `tokens.css`, at 1920×1080 on `#000`.
- Create `docs/design/demo/cards/record.py`, which uses the Playwright `record_video_dir` to produce `title.webm` and `end.webm`, then converts them to mp4 with ffmpeg.
- Add `--stage a,b` to `record.py`. It records the web verdict reveals from the lab fixtures, `http://127.0.0.1:8775/?stage=<name>&moment=verdict` at 960×1080 for 4 s, to `demo/clips/12a-partial.mp4` and `12b-slacked.mp4`. This is DEMO.md take W1.
- Render Pinch PNG stills (`celebrate`, `partial`, `supportive`, `hello` at 512) for ask A4 (the reel title card).
- **DoD:** `python3 docs/design/demo/cards/record.py` writes `demo/clips/00-title.mp4` and `99-end.mp4`. Run `ffprobe` and check they are 1920×1080 and 4.0 s.

---

## 8. Wave 2: integration and adversarial review (20:50–21:30)

### 8.1 Gate G2: L0 runs it at 20:50, and again after the fixes
```bash
./alibi.sh test | rg -c FAILED                                          # → 0   (includes test_pinch once ask A2 lands; else run it directly)
.venv/bin/python tests/test_pinch.py | tail -1                          # → test_pinch OK (16 cases)
python3 docs/design/tools/lint_design.py                                # → lint_design OK (0 findings, N files)
bash scripts/build_native.sh | tail -1                                   # → Built Alibi.app (…)
bin/alibi-island --snapshot /tmp/g2/island --state docs/design/fixtures/island/all.json   # → renders=N, N ≥ 12
for s in idle live_focused nudge_phone verdict_done verdict_partial verdict_slacked; do for t in dark light; do
  python3 docs/design/tools/render.py "http://127.0.0.1:8775/?stage=$s" /tmp/g2/web-$s-$t.png --w 1280 --h 1200 --wait 2800 --$t; done; done   # stderr empty
python3 docs/design/tools/render.py "http://127.0.0.1:8775/?stage=verdict_done&moment=verdict" /tmp/g2/rm.png --reduced-motion --dark --wait 2800
(cd ios && lockf -k /tmp/alibi-ios.lock sh -c 'xcodegen generate --quiet && xcodebuild -project AlibiPhone.xcodeproj -scheme AlibiPhone -destination "platform=iOS Simulator,name=iPhone 17 Pro" -derivedDataPath /tmp/alibi-g2 CODE_SIGNING_ALLOWED=NO build' | tail -1)   # → ** BUILD SUCCEEDED **
.venv/bin/python tests/test_ios_contract.py | tail -1                    # → its OK line
```
Assemble a contact sheet of every G2 render into `/tmp/g2/sheet.png` with Pillow, and give it to the three reviewers.

### 8.2 Adversarial reviewers (20:50–21:05, read-only, parallel)
Each reviewer reads the diff since `p16-design` and the G2 renders, then reports findings in three severities:
- **P0:** breaks the demo or the tests
- **P1:** visible in the demo, or an accessibility failure
- **P2:** polish, which is not fixed tonight

Each finding names its `file:line`, a one-line failure scenario and the fix.

| Reviewer | Hunts for |
|---|---|
| **V1 UX and copy** | Is there one idea per glance? Does any card carry two headlines? Is Pinch's copy 12 words or fewer, in the first person, with digits, no "!" and no emoji? Does every bad verdict end with a fix? Sentence case everywhere? Are the verdict glyphs and words paired? Does the nudge never shame? Is the idle empty state written? Does an offline state exist on all three surfaces? Does any text claim "frames never leave your Mac" while the witness is `nvidia`? Check with `./alibi.sh status` (CLAUDE.md privacy rule). |
| **V2 Accessibility** | Contrast of every text and surface pair against the RESEARCH §2.2 table in both themes, especially green ink on wash. Black on every green fill. A visible `focus-ring` on every control, with keyboard order on the dashboard (tab through it with Playwright `--eval`). `aria-label`s on icon buttons. Status shown by shape as well as colour. `prefers-reduced-motion`: fewer and gentler, not nothing, and Pinch still shows state. Dynamic Type at XXL on iPhone. VoiceOver labels on Pinch ("Pinch, celebrating") and on the ring. Is the Live Activity readable when the luminance is reduced? |
| **V3 Motion, performance and regressions** | Only `transform` and `opacity` animate. Every duration and spring comes from tokens. Closes never bounce. Is the 90 s Pinch cooldown honoured? Can a reload replay an event (seq diffing)? Can three clients double-fire? Is the rAF stopped when hidden? Does the island still allow click-through when collapsed, and still respond to hover dwell, ⌥⌘A, Esc and `--act`? Does polling cost the same as before (1 Hz state)? Is the camera off after `stage.py` exits? Are the `row("phone","app")` contract rows intact? Did the `alibi.sh` freshness check rebuild after a `Pinch.swift` edit? Did the `build_native.sh` diff touch only the island line? |

### 8.3 Fixes (21:05–21:25)
Lane owners fix P0, then P1, in their own files only, and commit per §9.1. A reviewer verifies each fix against its finding. Then L0 re-runs G2 at 21:25 and cuts the tags at 21:30.

---

## 9. Commit protocol

### 9.1 Every commit
```bash
git status --porcelain -- <your owned paths>          # see exactly what you changed
git add -- <exact paths you own>                      # never -A, never ., never -a
git diff --cached --name-only                         # must list only your paths; if not: git restore --staged <stray>
git commit -m "<pN area>: <what works now>"           # plain message, no trailers of any kind
```
- **No `Co-Authored-By`** or any other AI attribution line, in any commit, ever (user rule).
- **Never** use `stash`, `checkout -- .`, `reset --hard`, `rebase`, `push --force`, `commit --amend` on a commit you didn't just make, or `add -p`, which is interactive and unsupported.
- CLAUDE.md's `git add -A && git commit -m "pN works"` is **overridden tonight** by pathspec staging, because two sessions share the tree.

### 9.2 Tags (L0 only, after the DoD passes and G2 is green for that surface)

| Tag | When | Commit message |
|---|---|---|
| `p16-design` | Wave 0 DoD | `p16 design foundations: tokens, Pinch rig, web/Swift seams` |
| `p17-dashboard` | S1–S3 and M1–M3 (plus M4/M5 if shipped) and G2 web | `p17 dashboard works: dark-first all-sans, Pinch, verdict reveal, nudge card` |
| `p18-island` | I1–I5 and the G2 island snapshots | `p18 island works: springs, bloom, Pinch 16/28/56/64, nudge + verdict alerts` |
| `p19-iphone` | P1–P3 and the simulator build | `p19 iphone works: Today live mirror, Week, Health on tokens` |
| `p20-live-activity` | A3 DoD (device or simulator) | `p20 live activity works: Lock Screen + Dynamic Island with Pinch` |

Run `git tag <name>` on the commit that passed. Never move a tag; if a later fix lands, the tag stays where it is. These names never collide with the other session's `p0`–`p14` (ask A7).

### 9.3 Shared files: `alibi/api.py`, `alibi/integrations.py`, `ios/project.yml`, `CLAUDE.md`, `alibi.sh`, `scripts/build_native.sh`
1. **Before editing**, run `git diff --quiet -- FILE && echo clean`. Edit only when it prints `clean`.
2. Make the minimal edit, then commit **that file alone within 2 minutes** and post on the status board: `committed <file> (<n> lines)`.
3. **If the file is dirty** because the other session is mid-edit, do not touch it. Send them the exact diff with SendMessage to `nvidia-habits-fe`, and ask them to include it in their next commit. Then continue with stubs: the clients treat `pinch` as optional.

---

## 10. Cut order and fallbacks

**Cut in this order when a checkpoint is missed:**
1. **Live Activity.** At A0 no-go, use simulator only. If the simulator fails at 19:45, drop the lane.
2. **COULDs:** I7 `--stage`, the Quiet lobster toggle, S4 `signals.html`, the P4 icon, a light theme on the phone, `thinking`.
3. **S3 clips:** `surprise`, `listening`, `sleepy`, and their M5 and I2 hooks. Pinch keeps its moods.
4. **S2 motion:** M4 composer FLIP and polaroid develop, and I6 wings and peek.

**Never cut:** Wave 0, L1 S1–S2, L2 M1–M3, L3 I1–I5, L4 P1–P2, L6 K2–K4, G2 and the demo.

**Hard rules:**
- `p18-island` not tagged by 21:10: ship I1–I3 and keep the old nudge and verdict layouts, with Pinch dropped into them at 56/64.
- `p17-dashboard` not tagged by 21:10: tag what passes lint plus the verdict reveal. The demo uses `?stage=` fixtures for the web shots.
- Fixed at 21:30: recording starts no matter what.

---

## 11. Risks and mitigations

| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| R1 | The other session's uncommitted edits get swept into our commits, or ours into theirs | high / high | Pathspec staging, a `git diff --cached --name-only` check, the §9.3 protocol and asks A1/A7 |
| R2 | Live Activity provisioning fails: a 5th bundle ID on team 87P4DWU22Q, App ID limits, 7-day profiles | medium / medium | A0 runs first with a go/no-go at 19:20, then a simulator-only fallback. Nothing else depends on L5. |
| R3 | **The iPhone 14 has no Dynamic Island** | certain / low | Lock Screen shots come from the real phone, and Dynamic Island shots from the iPhone 17 Pro simulator (DEMO.md). |
| R4 | The phone gets 401 from a stage daemon, because each data dir has its own `phone_secret` | high / high for the demo | `stage.py --phone` copies the main secret and enables sync. Pre-flight checks `curl -s -H "X-Alibi-Secret: …" :8766/api/phone/session`. |
| R5 | `Color(hex:)` ambiguity, or a top-level symbol collision when `Theme` and `Pinch` join `Island.swift` | certain / medium | Wave 0 step 4 deletes the Island extension and runs the collision `rg`. `main.swift` holds the only top-level code. |
| R6 | Legacy CSS variable names collide with the token names (`--bg`, `--ink`, `--accent`, `--warn`…) | certain / medium | `tokens.css` is not linked until S1, which replaces the legacy `:root` with a compatibility block. |
| R7 | Pinch double-fires or replays across three clients and page reloads | medium / high | A server `seq` (Appendix B), "record without playing" on first load, the engine's 90 s cooldown, and reviewer V3's check |
| R8 | Reduced Motion is on, on the demo Mac, and hides the celebrations | low / high | Pre-flight checks Accessibility → Display → Reduce motion is off. Every moment has a fade fallback anyway. |
| R9 | `./alibi.sh down` or `demo`, run by anyone, kills every daemon, including the lab daemon and the other session's | medium / medium | Banned in Waves 0–2 (§3.3). The lab uses its own port and data dir. |
| R10 | Concurrent `xcodegen` or `xcodebuild` corrupt the shared `.xcodeproj` | medium / medium | The `lockf /tmp/alibi-ios.lock` wrapper and per-lane derived data. Ask A8 asks the other session to use the same lock. |
| R11 | Real-camera recognition is flaky in the take: Apple Vision misses the phone | medium / high | The phone is held face-on in frame for 40 s. A fixture take (`stage.py done`) covers the nudge and verdict, with the LIVE frame kept out of shot (DEMO.md). |
| R12 | Scope creep in polish | high / high | Hard boxes, the 20:50 freeze, and the cut order. The demo hour is never borrowed. |
| R13 | A stale `CLAUDE.md` copy makes an agent re-introduce serif type | medium / medium | Wave 0 rewrites the section first. The `serif-*` lint rules fail the DoD. |
| R14 | Stale browser cache shows old CSS while recording | medium / low | Hard-reload in pre-flight. L1 appends `?v=p16` to its `<link>` and `<script>` URLs at tag time. |

---

## 12. Asks to the other session (`nvidia-habits-fe`)

Send this message at 18:30, right after Wave 0's gate. Each ask is small, and none blocks a MUST.

> Redesign session here. Our lanes start 18:50 (plan: docs/design/IMPLEMENTATION.md §4 ownership, §12 asks). We will only touch files we own; for shared ones we commit one file at a time when `git diff --quiet` says clean, else we send you the diff. Asks:
> **A1 (now)** Please commit or tell us before 18:30 when `ios/project.yml`, `scripts/build_native.sh`, `alibi.sh`, `CLAUDE.md`, `alibi/web/**`, `native/Island.swift` are clean. Wave 0 edits: build_native.sh (island compile line → 5 files incl. new native/main.swift), alibi.sh (freshness check), project.yml (3 source lines in AlibiPhone; later the new AlibiLive target + `- target: AlibiLive` + `NSSupportsLiveActivities: true`), CLAUDE.md (Design system section only).
> **A2** Add `test_pinch` to the list in `tests/run_all.sh` once `tests/test_pinch.py` lands (~19:35). Our K3 adds one line in `api.py state()` (`out["pinch"] = pinch.current(out)`) and one key in `integrations.py phone_session()` (`"pinch"`); if you already reserved a `pinch` slot, tell us and we fill it instead.
> **A3** `/api/phone/session`: keep the flat keys SyncEngine reads (`active, habit, label, ends_at, shield, on_break, sync_every_s`) and add the agreed `session.{id, habit, habit_label, modality, started_at, ends_at, declared_min, on_break, on_task_ratio, last_label, drifting, nudges}`, `today`, `recent_verdict`, `streak_days`, `plan_next`. Plus, if cheap: `week: [{date, claimed_min, seen_min, verdict}]` ×7 for the phone's Week tab.
> **A4** In your files, when you have 10 min: `evidence.py` — verdict pill black text on green (`:47`), contact-sheet type NewYork → SF Pro/Helvetica Neue (all-sans now), COLOURS on the new palette (retire `#C8362B`; absent `#A6A6A6`); `routes_integrations.py` page CSS on our tokens (read `alibi/web/css/tokens.css` at import and inline it on the `:8766` pages; dark-first, sans); `reel.py` title card with Pinch from `docs/design/demo/cards/pinch-*.png` (lands ~20:50).
> **A5** OK for us to add `ios/AlibiPhone/Assets.xcassets/AppIcon.appiconset` and set `ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon` in the AlibiPhone target?
> **A6** (optional) `AlibiPhoneApp.swift` forces `.preferredColorScheme(.dark)`; leave it for tonight.
> **A7** Please don't tag `p16*`–`p20*`, don't `git add -A`, and don't touch alibi/web/**, native/Island.swift, native/main.swift, native/Theme.swift, native/Pinch*.swift, ios/AlibiPhone/Views/**, ios/AlibiLive/**.
> **A8** For iOS builds, please wrap xcodegen/xcodebuild in `lockf -k /tmp/alibi-ios.lock …` like us, and use your own `-derivedDataPath`.
> **A9** From 21:30 to 22:45 we own the running daemon on :8765/:8766 and the camera for recording — please don't run `./alibi.sh up|down|demo` then.
> **A11** (optional) `nudges.py` `LINES` in Pinch's voice: "You said {habit}. I've seen your phone for {mins}." / "…the desk has been empty for {mins}." / "You said {habit}. That's been {title} for {mins}."; `SECOND` → "Second nudge. I'll note it in tonight's report." Our clients compose the line themselves, so this is only for banners and the reel.
> **A10** (optional) emit `notify(kind="synced", text=…)` on Health ingest and Strava sync so Pinch's `connected` clip has a real event.

---

## Appendix A: `CLAUDE.md` "Design system" section (replacement text, verbatim)

```markdown
## Design system — Alibi redesign (dark-first, all-sans, Pinch)

Source of truth: `docs/design/system/project/` (README, Motion, Mascot, tokens.json); build plan `docs/design/IMPLEMENTATION.md`.
Token files: web `alibi/web/css/tokens.css`, Swift `native/Theme.swift` (`enum Alibi`; shared with iOS via project.yml),
mascot `alibi/web/js/pinch.js` + `native/Pinch.swift`/`PinchData.swift`. Don't hand-copy values; use token names.

- **Type: all sans, no serif anywhere** (no New York, Source Serif, Newsreader, Georgia; no italics). SF Pro / system
  stack (`--font-sans`, Onest as the web fallback), SF Pro Rounded for big numerals (`--font-rounded`), SF Mono only for
  keycaps and IDs. Every number uses tabular figures. Pinch's lines use the `voice` style (20/1.45 w500). Sentence case
  everywhere; the only caps are the island wordmark "ALIBI".
- **Dark first:** bg `#000`, surface-1 `#1A1A1A`, surface-2 `#262626`; light is a full second theme (`data-theme`).
- **Colour:** accent `#76B900` ≤5% of chrome (Pinch exempt); text on any green or red fill is `#000`; green text uses
  `accent-ink` (`#4E7A00` light / `#8FD400` dark; `#477200` on green wash). Warn `#E5484D` (ink `#C4161C`/`#FF7A7E`),
  partial/idle `#F2A900` (ink `#8A5F00`/`#FFC233`). Status colour always ships with a shape (● on task, ○ idle, ■ phone,
  hatched off task, dashed absent); verdicts are `✓ Done` · `◐ Partly` · `✕ Slacked`. No gradients except the one
  celebration `bloom`. No custom glass.
- **Motion:** six springs (micro, snappy, smooth, island, bouncy, celebrate) and durations 120/180/260/420 ms from tokens;
  transform + opacity only; closes never bounce; never ease-in; reduced motion = fewer and gentler, not none.
- **Pinch** (original green detective lobster with a lens; never "Nemo"): sizes 16/20/28/32/44/56/64/96/160 only; moods
  idle, focused, listening, thinking, sleepy, reading; clips hello, sideeye, nudge, celebrate, partial, supportive,
  surprise, connected; one clip per 90 s, verdict > nudge > correction > connected > hello; driven by `state.pinch`
  `{mood, event, seq}` from `alibi/pinch.py`. Honest, never shaming; ≤12 words, first person, digits, no "!" or emoji.
- **Island sizing:** collapsed = notch (wings notch + 2×46 pt while live), expanded 400 pt, nudge 400 pt, verdict 440 pt,
  open radius 28 with 12 pt padding (inner cards 16). Hover opens after a 0.35 s still dwell; it only folds once the
  pointer has been outside a margin (32 pt each side, 48 pt below) for 0.8 s, and a click inside pins it open until Esc /
  send / click elsewhere. Keep it forgiving: never make the leave zone tighter than the drawn island.
- Check with `python3 docs/design/tools/lint_design.py` (must end `lint_design OK`).
```

## Appendix B: Pinch rulebook (`alibi/pinch.py`)

```python
def pinch_state(state: dict, prev: dict | None) -> dict:
    """state = the /api/state payload (without "pinch"); prev = this function's previous return (or None).
    Returns {"mood": str, "event": str | None, "seq": int, "ref": str | None}. Pure: no I/O, no clock."""
```

**Event** (the identity is `ref`; `seq = prev.seq + 1` only when `ref` differs from `prev.ref`, otherwise `event`, `seq` and `ref` carry over):

| Latest `state.alert` (new `id`) | `event` | `ref` |
|---|---|---|
| `kind == "verdict"`, `verdict == "done"` | `celebrate` | `alert:<id>` |
| `kind == "verdict"`, `verdict == "partial"` | `partial` | `alert:<id>` |
| `kind == "verdict"`, `verdict == "slacked"` | `supportive` | `alert:<id>` |
| `kind == "nudge"`, `label == "phone"` (and `session.nudges ≤ 3`) | `nudge` (clients chain `sideeye` → `nudge`) | `alert:<id>` |
| `kind == "nudge"`, any other label (and `session.nudges ≤ 3`) | `sideeye` | `alert:<id>` |
| `kind == "nudge"` with `session.nudges > 3` | `None`: the alert still shows, Pinch holds `focused` | `alert:<id>` |
| `kind == "synced"`, or `kind == "info"` with `text` starting `"Strava:"` | `connected` | `alert:<id>` |
| `kind == "planned"` | `hello` | `alert:<id>` |
| `report`, `recap`, `pace`, other `info`, or no alert | no new event | unchanged |

**Mood** (first match wins):

| Condition | `mood` |
|---|---|
| `session` and `session.on_break` | `sleepy` |
| `session` and `session.warming_up` (fewer than 6 samples, so evidence is still being gathered) | `thinking` |
| `session` and `session.drifting` | `thinking` (the wings still show the side-eye pose, from `session.drifting`) |
| `session` | `focused` |
| no session, latest alert is `report`/`recap` and less than 120 s old (`now - alert.ts`) | `reading` |
| otherwise | `idle` |

Client-only moods, which the server never emits: `listening` (composer focus) and `sleepy` after 10 min with no interaction.

**Clients:**
- Keep the `lastSeq` seen on this surface. On first load, store it **without playing**.
- Play only when `seq > lastSeq`. Verdict clips and the chained `nudge` use `force`.
- Use `current(state)` behind a lock, so one daemon serves the dashboard, island and phone with one `seq`.

## Appendix C: iPhone models (`ios/AlibiPhone/Views/Mirror/PhoneSession.swift`, `Views/Live/AlibiLiveAttributes.swift`)

```swift
struct PhoneSession: Decodable, Equatable {             // every field optional: today's flat reply also decodes
    struct Live: Decodable, Equatable {
        var id: Int?; var habit: String?; var habit_label: String?; var modality: String?
        var started_at: Double?; var ends_at: Double?; var declared_min: Int?; var on_break: Bool?
        var on_task_ratio: Double?; var last_label: String?; var drifting: Bool?; var nudges: Int?
    }
    struct Pinch: Decodable, Equatable { var mood: String?; var event: String?; var seq: Int?; var ref: String? }
    struct Verdict: Decodable, Equatable { var id: Int?; var habit_label: String?; var verdict: String?; var on_task_ratio: Double?; var summary: String? }
    struct Day: Decodable, Equatable { var date: String; var claimed_min: Int?; var seen_min: Int?; var verdict: String? }
    var active: Bool?; var label: String?; var ends_at: Double?          // flat keys SyncEngine already reads
    var session: Live?; var today: [String: JSONNumberOrString]?          // decode `today` leniently (or skip it)
    var recent_verdict: Verdict?; var streak_days: Int?; var plan_next: [String: String]?
    var week: [Day]?; var pinch: Pinch?
}
```

`JSONNumberOrString` is a 10-line enum that decodes a number or a string. `drifting` may arrive as an object (`{label, since_s, samples}`) rather than a Bool. Decode it with a tolerant wrapper, so that a non-null value means `true`, plus `label`.

```swift
import ActivityKit
struct AlibiLiveAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var start: Date; var end: Date
        var onTask: Int                 // 0–100
        var status: String              // "on" | "drift" | "break" | "done" | "partial" | "slacked"
        var line: String                // "On task 92% · last seen 18:04" (≤ 40 chars)
        var pose: String                // Pinch still pose: focused | sideeye | sleepy | celebrate | partial | supportive
    }
    var habit: String                   // "Drawing"
}
```

The payload stays far below the 4 KB limit.

## Appendix D: `window.AlibiMoments` (web hook contract; Wave 0 ships the stub)

```js
// alibi/web/js/moments.js — loaded before app.js. L2 replaces the bodies; signatures are frozen.
window.AlibiMoments = {
  state(s) {},                                   // every poll, after render; drives Pinch from s.pinch
  verdict(rv, cardEl, opts = {animate: false}) {},  // after renderVerdict paints the card
  nudge(alert, s) { return false; },             // true = moments rendered the nudge card; app.js skips the red toast
  sample(label, imgEl, dotEl) {},                // a new sample appeared in the live strip
  sessionStart(fromEl, toEl) {},                 // composer → live card (FLIP)
  correction(sid, ts, label, dotEl, reply) {},   // after POST /api/sessions/{id}/correct succeeds
};
```

**Call sites in `app.js`.** Wave 0 inserts these; the numbers are lines in the pre-split `index.html`.
1. `pollState()` (911), after `handleAlert(...)`: `AlibiMoments.state(s);`
2. `renderVerdict(rv, anim)` (1073), at the end: `AlibiMoments.verdict(rv, $("#now"), {animate: !!anim});`
3. `handleAlert()` (1146), right after the `fresh` checks: `if (kind === "nudge" && AlibiMoments.nudge(a, s)) return;`
4. `renderNow()` (951), where `seenLabels` grows: `AlibiMoments.sample(label, imgEl, dotEl);` Pass `null` for the elements if they aren't handy, and L2 will query them.
5. `say()` (885), when the reply starts a session (`/^Started\b/` or a session id appears on the next poll): `AlibiMoments.sessionStart($("#composer"), $("#now"));`
6. `correct()` (about 1566), on success before `showToast`: `AlibiMoments.correction(sid, ts, label, null, j.reply);`
