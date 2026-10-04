# Changelog

**English** · [Русский](CHANGELOG.ru.md)

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versions follow [Semantic Versioning](https://semver.org/).

## Unreleased

### Added

- **Kick and YouTube tabs**, each with its own theme and chat preview.
  Kick: emote PNG 500×500 or animated GIF, sub badge 36/72 px. YouTube:
  member emoji 480×480 and member badge 128×128.
- **Files from links.** Paste a link with `Ctrl+V`, drag it from a browser
  or use "Add from a link…" in the queue menu. A direct link to a file
  works, and so does a 7TV, FFZ or Giphy page or any page with a picture.
  A picture copied in a browser keeps its animation.
- **One-click update.** In an installed copy the update link downloads the
  new version, checks it and installs it; the app restarts by itself.
- **Animation in the interface.** Short animations and videos (up to 10 s)
  play in queue thumbnails and the chat preview — now video, APNG and
  animated AVIF too; long videos show a single frame, and a still preset
  shows the frame that goes into the file. Only visible thumbnails play,
  and everything pauses while the window is minimized. Turn it off in the
  version menu.
- **A link field above the queue**: paste a link and press Enter.

### Changed

- The version number and the language moved to the top-right corner. The
  version number opens its menu with a plain click; the menu looks like the
  drop-down lists and appears with the same smooth animation.
- The window is at least 1010 px wide (was 980): seven tabs need the room.

### Removed

- **BTTV emote preset**: BTTV users have moved to 7TV.

## 1.2.2 — 2026-10-04

### Changed

- Updated app icon.

## 1.2.1 — 2026-10-04

### Changed

- **The update check runs on every start** instead of once a day: a new
  release no longer goes unnoticed for up to a day. A version found earlier
  is shown immediately, even before GitHub answers, so the link doesn't
  disappear without a network connection. The time of the previous check
  (`last_update_check`) is removed from the settings.

## 1.2.0 — 2026-10-03

### Telegram stickers (.tgs)

- **New input format — Telegram animated stickers `.tgs`** (Lottie).
  They convert to GIF, APNG, video (MP4, WEBM, AVI), a PNG/JPG/WEBP frame
  and every preset: Telegram video sticker and emoji, Discord emoji and
  stickers, Twitch, 7TV and BTTV emotes, WhatsApp sticker. Frames are
  rendered by rlottie — the same library Telegram uses; the vector artwork
  is drawn straight at the needed size. The default format is GIF.
- A sticker gets a thumbnail and duration in the queue and plays in the chat
  preview. The thumbnail and preview use a frame from the middle: the first
  frame of many stickers is empty.
- Exact duration: rlottie counts frames including the last one, and a
  3-second sticker would come out at 3.02 s with a duplicate frame at the loop.
- A damaged file gives a clear error with the file name instead of a crash;
  without the rlottie library there is a hint on how to install it.
- New dependency `rlottie-python` (LGPL 2.1, ~1 MB in the build); its license
  text is placed next to the exe.

### Documentation

- The README is four times shorter (436 → 108 lines): download, features,
  platform requirements in one table, running, building, licenses. Internal
  details and an outdated line saying `.tgs` was not supported were removed.
- A screenshot of the app window at the top of the README
  (`docs/screenshot.png`).
- The README is in two languages: `README.md` — English (shown by GitHub on
  the project page), `README.ru.md` — Russian; a language switch at the top.

### Chat preview

- **Twitch looks like the real chat**: below the messages there is a "Send a
  message" box and a channel points row with a "Chat" button. The names are
  "twitch" with a diamond badge and "DJClancy" with a check-mark badge (the
  badges are drawn in code, no files needed). The sub badge preset puts the
  user's picture in place of these badges, the channel points preset — in the
  points row next to the number, where Twitch shows the channel points icon.
  The user's own emote also appears in the input box.
- **Telegram, emoji**: as in Telegram itself — "rate my new emoji" with the
  emoji and the time inside the bubble, below it a large emoji without a
  bubble and the time in a pill on the right.
- **Discord**: the message is written by "Discord" with its logo as the avatar.
- All scenes show the same message time — 18:04.

### Tests

- **Test windows are not shown on screen** (`WA_DontShowOnScreen` in
  `tests/language_pin.py`): a test run doesn't flash windows or steal focus.
  Font metrics are real — the `offscreen` platform can't see fonts on
  Windows. To show the windows: `DTT_SHOW_TEST_WINDOWS=1`.
- The layout and corner suites occasionally (about 7 runs in 100) crashed
  with an access violation after printing their result: `sys.exit` was called
  right from a timer handler, and windows were torn down in random order as
  Python exited. Now the loop ends with `app.exit` and windows are deleted
  explicitly while the application is alive. For the same reason `main.py`
  deletes the window explicitly — 40 app closes showed no crash even before,
  this is a safeguard.

### Number fields

- Spin box buttons are thin chevrons inside the field instead of a grey
  column with a divider and filled triangles; they highlight on hover and dim
  at the end of the range. Dropdowns use the same chevrons.
- Time fields are wider (trim 108 px, Telegram fragment 90 px): "1250.50 s"
  for a long clip used to be cut off.

### Accessibility

- **Visible keyboard focus**: the focused element has a white border, a toggle
  has a white outline around its track. Focus used to be invisible on every
  element. Buttons take focus only from the keyboard, so there is no border
  after a mouse click. An empty `Tab` stop on the scroll area was removed.
- **Disabled fields look disabled**: dimmed text and border on the field and
  its label. "Width: Auto" used to look editable with its toggle off.
- **Contrast**: the "Start" button (4.3 → 5.4), the version number (2.3 → 4.9),
  the empty queue hint, group headers in the format list, captions in the
  Telegram preview — all at least WCAG AA 4.5:1. Field borders, the toggle in
  its off state and the dashed border of the empty queue — at least 3:1.
- Field labels are linked to their fields; tabs, lists and the preview have
  names and descriptions for screen readers. The version number menu opens
  from the keyboard (`Tab`, then `Enter`).
- Settings group headers are 11 px instead of 10, preview captions too.

### Fixed

- **A square behind dropdowns**: the dropdown's container window was filled
  with a rectangular panel and cast a rectangular shadow, so a dark square
  showed behind the rounded card. The container is now transparent and has
  no system shadow. The list opens below the field (normal mode rather than
  a "menu" over the field): in menu mode Qt draws that panel bypassing the
  style sheet.

### Changed

- **The queue never scrolls sideways**: a long name is shortened in the
  middle, while the target format and the status icon are always visible.
  The icons used to slide off the edge as soon as one row was longer than the
  list — exactly when it contained an error message. The icons differ by
  shape (○ ● ✓ ✕ ■), not only by colour; the status in words is in the row's
  tooltip.
- **The bottom row is not cut off**: the processing summary is shortened with
  an ellipsis (in full in the tooltip), the update link takes the place of the
  version number, the toggle is called "Overwrite files".
- **Platform tabs**: a preset is applied on click, so the "Apply…" buttons
  there were replaced with a note saying which files it applies to. Until a
  platform preset is selected, the callout says so and the preview is dimmed —
  before, they described a preset that was not being applied.
- Confirmations with "Reset / Cancel" and "Create frames / Cancel" buttons
  instead of the untranslated "Yes / No".
- Decimal numbers use the interface language's separator both in fields and
  in captions ("3.5 s" / "3,5 сек"); Russian plurals are inflected properly.
- Texts: "Limit file size" instead of "Fit into size", "Trim" instead of
  "Change duration", presets "PNG sticker" instead of "Sticker PNG", platform
  formats named by one scheme ("Telegram: PNG sticker"). The Russian interface
  got clearer wording too ("resolution" and "file size" instead of two
  different "sizes", "Remove selected" instead of "Delete selected"). Error
  messages say what to do.

## 1.1.0 — 2026-10-03

### Added

- **Platform tab themes**: on the Telegram, Twitch, Discord and WhatsApp tabs
  the settings panel takes the platform's own colours with a smooth
  transition. Only colours change; the layout stays in place.
- **Chat mock-up preview**: the selected file is shown as it will look in
  chat — a Twitch emote in a chat line at 28 px, a Discord emoji in a message
  and large, Telegram and WhatsApp stickers in a conversation. GIF and
  animated WEBP play, rotation and flipping show immediately.
- **WhatsApp tab**: WEBP sticker 512×512 up to 100 KB, animated sticker up to
  500 KB and 10 seconds, pack icon 96×96.
- **Twitch subscriber badges** (18/36/72) and **channel points reward icons**
  (28/56/112), each file up to 25 KB.
- **7TV and BTTV emotes**: an animated result from video and animations, PNG
  from a still picture.
- **"Fill the square" mode** for square presets: the picture fills the square
  and the edges are cropped instead of leaving transparent margins.
- **Paste from the clipboard (Ctrl+V)**: a picture, files or a file path go
  straight into the queue.
- MKV, MOV, M4V, WMV, FLV, MPG, 3GP, OGV and TIFF are accepted as input.
- A daily check for a new version on GitHub: a link appears next to the
  version number. Turn it off in the version number's context menu.
- Windows installers (`build_windows.ps1 -Installer`, Inno Setup 6) — with and
  without FFmpeg: a Start menu shortcut, uninstall via "Apps", upgrade in place.

### Changed

- Animated emotes and stickers are built faster. A Twitch GIF set:
  4.4 → 0.9 s, animated WEBP → Telegram sticker: 7.4 → 3.0 s. Frame rate and
  quality search starts from the best option and recalculates the next
  attempt from the file size, a short GIF is built in a single FFmpeg run,
  and the smaller sizes of a Twitch set take the frame rate of the largest.
- All sizes of a Twitch set are animated at the same frame rate.
- Processing error messages are translated: in the English interface they no
  longer appear in Russian and follow the window's language.
- "Reset" no longer touches the language and the update check setting.
- Small notes have better contrast (WCAG AA).

### Fixed

- An animated Discord sticker ignored the trim end: a "from 2 s to 3 s"
  fragment came out five seconds long.
- An animated Twitch emote from a long clip silently turned into a slideshow
  of a couple of frames per second — now a warning appears before the start,
  suggesting to trim a fragment.
- Running the tests no longer resets the app's own settings: tests use a
  separate profile.

## 1.0.0 — 2026-08-06

The first public release. Before it the app was called Media Converter Studio
and was in beta.

### Added

- **Discord stickers and emoji**: static PNG and animated APNG 320×320 for
  stickers, PNG and GIF 128×128 for emoji. APNG keeps full 8-bit
  semi-transparency, so soft edges don't turn into a fringe.
- **Twitch emotes**: PNG and GIF, single size or a 28/56/112 set.
- **Telegram stickers and emoji** to the official spec: static PNG/WEBP,
  video WEBM/VP9 up to 3 seconds and 256 KB.
- **Audio**: extract the track to MP3, M4A (AAC) or WAV, pick the bitrate,
  "remove audio" toggle. Trimming works for audio too.
- **APNG** as an output format: unlike GIF, it keeps all colours and
  semi-transparency.
- **English interface**, switched on the fly — the queue, settings and the
  selected preset are kept.
- Quality slider (1–100) and a "fit into size" mode: the bitrate is chosen to
  hit the given number of megabytes.
- Rotation by 90/180/270° and flipping, including on top of platform presets.
- Checkboxes in the queue: only checked files are processed.
- Trimming is set by start and end rather than start and length.
- CSV report, remaining time estimate, a notification when the window is
  minimised.
- A log file and an error window instead of crashing silently.

### Changed

- Animated WEBP, AVIF and APNG are detected by file contents, not by
  extension: 7TV and BetterTTV emotes convert just like video, keeping the
  original speed and semi-transparency.
- The intermediate format for animation is MOV with the qtrle codec instead
  of GIF: GIF has 1-bit alpha, and semi-transparent edges turned into a ragged
  fringe. Measured: via GIF 2 % of semi-transparent pixels survived, via
  qtrle — 52 %.
- Thumbnails and file durations are computed in the background. Adding a
  folder of 200 photos: 7.14 s before, 0.16 s now.
- The queue is processed in parallel: images in four threads, video in two —
  FFmpeg already uses all cores.
- The build moved from `--onefile` to `--onedir`: the exe no longer unpacks
  itself into a temp folder on every start, so it starts faster and triggers
  fewer antivirus false positives.
- All processing options are on one tab; the selected format is not reset
  when switching tabs.
- Quality and "fit into size" are shown only where they work: JPG, WEBP, AVIF
  and video. PNG, BMP, GIF, APNG and audio have nothing to tune, and these
  fields used to silently do nothing there.

### Fixed

- The source file is never overwritten by the result — even with overwriting
  on and the same folder. An animated WEBP used to overwrite itself.
- The format list lost the JPG item after a language switch if a platform
  preset was selected.
- A language switch lost a multi-file selection and a chosen but not yet
  applied format: "Apply to all" used the old one.
- Frame export of two files with the same name from different folders wrote
  into one folder, overwriting each other.
- An interrupted file stayed in the "Processing" state forever with a frozen
  percentage.
- Thumbnails are prepared as QImage: QPixmap is a paint device, and Qt does
  not promise it works outside the GUI thread.
- The queue worker got an owner: the thread object could be destroyed while
  the thread was still running.
- Cyrillic file names no longer break conversion.
