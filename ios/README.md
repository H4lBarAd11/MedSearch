# MedSearch for iOS

The desktop app's own engine (`app.py`) and interface (`templates/`, `static/`),
run inside an iOS app by CPython for iOS and shown in the system web view. The
shell is `src/medsearch/shell.py`; everything else is copied in from the
repository root at build time (see `sources` in `pyproject.toml`), so a change
to the desktop app is a change to this one.

Spike of 19 October 2026: the unchanged engine starts in the app, the page
renders, and a PubMed search comes back over HTTPS (iPad Pro 11-inch
simulator, iOS 27).

## Building

Briefcase lives in its own virtual environment here (`.venv/`, not committed).
Xcode and the iOS simulator runtime must be installed.

```
python3 -m venv .venv && .venv/bin/pip install briefcase
(cd .. && .venv/bin/python render_icon.py ios)   # icons/: the app icon and launch screen
.venv/bin/briefcase create iOS
python3 patch_xcode.py       # quotes a path in the build phase; renames and lays out the launch image
.venv/bin/briefcase build iOS
.venv/bin/briefcase run iOS -d "iPad Pro 11-inch (M5)"
```

After a change to the shell or the engine: `briefcase build iOS -u` copies the
sources in again before building. `briefcase create iOS` regenerates the Xcode
project (and needs `patch_xcode.py` again); a change to `pyproject.toml`'s
`info` keys needs it too. `icons/` holds the desktop's own drawing at every
size iOS asks for (`render_icon.py` writes them); without it Briefcase ships
its own icon. The launch screen is Briefcase's storyboard, reduced by `patch_xcode.py` to the
interface's ground (a named colour, light and dark), with no image: his phone
(iOS 27.1 beta) drew the storyboard's ground and never its image, and the
Info.plist form (`UILaunchScreen`) came out white in the simulator (19 Oct).
The drawing is the shell's own splash (`Splash` in shell.py), put up over that
ground once Python runs and faded off when the page is ready.

To open on a search, as the desktop's `--query`: the environment variables
`MEDSEARCH_QUERY` and `MEDSEARCH_SOURCE`. The simulator passes them through as
`SIMCTL_CHILD_MEDSEARCH_QUERY="awake craniotomy" briefcase run iOS ...`.

## On a device

`briefcase open iOS` opens the Xcode project. With an Apple ID added under
Xcode › Settings › Accounts, its Personal Team signs the app for a device
plugged into this Mac (no paid account: the install lapses after 7 days, up to
3 such apps on the device, no TestFlight). Pick the device and the team under
Signing & Capabilities, then Run. From the terminal, the same build and
install (Briefcase itself runs simulators only):

```
xcodebuild -project build/medsearch/ios/xcode/MedSearch.xcodeproj -scheme MedSearch \
    -destination "id=<device UDID>" -allowProvisioningUpdates \
    DEVELOPMENT_TEAM=<team id> CODE_SIGN_STYLE=Automatic build &&
xcrun devicectl device install app --device <device UDID> \
    ~/Library/Developer/Xcode/DerivedData/MedSearch-*/Build/Products/Debug-iphoneos/MedSearch.app &&
xcrun devicectl device process launch --terminate-existing --device <device UDID> com.halbarad.medsearch
```

Chained with `&&`: a build that fails (the phone locked, asleep or off the
Wi-Fi: Xcode will not build for a device it cannot reach) must not go on to
install, or the last build goes onto the phone again (20 Oct).
`xcrun devicectl list devices` gives the UDID; the team id is under the Apple ID in
Xcode's Accounts (a freshly created project remembers no team). The phone must be unlocked for
the launch; the first launch of a Personal Team app needs the developer
trusted under Settings › General › VPN & Device Management.

The engine's files live in the app's own Library/Application Support/MedSearch
(the container's root, where `~/.medsearch` would be, is read-only on a
device; the simulator allows it, so a simulator proves nothing here).
Exports and saved PDFs go to Documents, which the Files app shows.

## What the shell provides

- The chrome in the system's own Liquid Glass (`src/medsearch/chrome.py`):
  the search pill, the sources pill and the dock are UIKit glass views over
  the page (UIVisualEffectView + UIGlassEffect, the thin material before
  iOS 26). The page hides its own three bars (`html.native-chrome` in
  touch.css) and reports its state through the bridge: the sources label,
  the query, which dock button is on, whether a sheet is open (the chrome
  steps aside). A tap on the native dock clicks the page's hidden button.

- The page's `window.pywebview.api.open_external` and `window.open`, and any
  link that would leave the engine's pages: an SFSafariViewController, the
  system's in-app browser, with the person's Safari sign-ins (the library
  proxy's among them), a PDF reader and Share.
- The Keychain: `secrets_store` goes through `secitem.py` (Security.framework
  via rubicon-objc) on iOS, each item marked for iCloud Keychain. The library
  setup (the institutions' proxy addresses, the active one, the library
  resources) travels the same way, as one item (`library_setup`) stamped
  with when it was saved: at each launch and each save the newer of the
  two devices' wins. The history, the ticked databases and the saved
  sign-ins stay on the device (app.py, `_sync_library_setup`).
- The splash: the icon's drawing on the interface's ivory, put up by the
  app itself the moment its window exists and faded off when the page says
  it is ready, as the Mac's splash. The launch screen before it is the
  same ivory (what the system makes of a launch screen's image varies by
  device and version; `patch_xcode.py` tells the story).
- No title bar: the page takes the screen, status bar included, and
  `static/css/touch.css` lays it out for a phone (one column, glass bars
  above the safe areas, sheets for panels and dialogs, the system text size).
- `MEDSEARCH_SELFTEST=hold` keeps the launch screen up ten seconds, for
  `xcrun devicectl device capture screenshot`; `MEDSEARCH_SELFTEST=net` logs every
  name lookup and socket the Python side opens (nettrace.txt beside the config);
  `MEDSEARCH_SELFTEST=keychain` writes a Keychain round trip to
  `Library/Application Support/MedSearch/selftest.txt` in the app's container; `MEDSEARCH_SELFTEST_JS="<script>"` runs that script
  in the page once it is up (a panel, a dialog, the in-app browser), since a
  simulator cannot be tapped from the terminal. Checks, not features.

## Not there yet

- iCloud Keychain sync with the Mac works only for a Mac build signed by the
  same team (`MEDSEARCH_TEAM=<team> packaging/build-mac.sh`, which runs
  packaging/sign-mac.sh): a personal team's profile lasts seven days, a paid
  Developer ID a year. The public download is unsigned and keeps its keys in
  the login keychain, as before.
- Saving a PDF from the page's own viewer (the desktop writes to Downloads).
- The update check (the Store, or Xcode, updates the app).
