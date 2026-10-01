# native/shared

SwiftUI-only Swift files shared by the macOS notch island and the iPhone app (for example `Theme.swift`,
`Pinch.swift`, `PinchData.swift`).

- **Island:** `scripts/build_native.sh` compiles every `native/shared/*.swift` together with `native/main.swift`
  and `native/Island.swift` into `bin/alibi-island` (and `Alibi.app`). `./alibi.sh up` rebuilds when any of them
  is newer than the app.
- **iPhone:** `ios/AlibiPhone/Views/Shared/` holds copies. This folder is the source of truth: edit here, then run
  `bash scripts/sync_shared_swift.sh` to copy the files across. Don't edit the copies.

Rules for files in here:
- `import SwiftUI` (and Foundation) only: no AppKit or UIKit, so the same file compiles on macOS and iOS.
- No top-level statements (only `native/main.swift` may have them); declarations only.
- No app state, networking or daemon calls. Views, colours, shapes and plain data types.
