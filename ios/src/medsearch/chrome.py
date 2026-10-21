"""The native chrome: the search pill, the sources pill and the dock as real
UIKit glass over the page (his ask, 19 Oct: the system's own Liquid Glass,
not a drawing of it in CSS).

On iOS 26 a UIVisualEffectView with a UIGlassEffect IS the material: the
lensing, the light on the rim, the motion. The page hides its own three bars
(html.native-chrome in touch.css) and keeps everything else, and the two
sides talk through the bridge in shell.py: a tap here clicks the page's
hidden button; the page reports the sources label, the query, which dock
button is "on", and when a sheet should hide the chrome.

Frames, not constraints: the shell already hears every native layout pass
(the window's top inset hook) and lays the three bars out again from the
window's bounds and safe-area insets. On an iOS before 26, the same bars in
the system's thin material: not glass, but the system's own.
"""

from __future__ import annotations

from rubicon.objc import Block, NSObject, ObjCClass, SEL, objc_method, objc_property
from rubicon.objc.types import CGRectMake, CGSizeMake

UIView = ObjCClass("UIView")
UIVisualEffectView = ObjCClass("UIVisualEffectView")
UIButton = ObjCClass("UIButton")
UIImage = ObjCClass("UIImage")
UIImageView = ObjCClass("UIImageView")
UIImageSymbolConfiguration = ObjCClass("UIImageSymbolConfiguration")
UIColor = ObjCClass("UIColor")
UIFont = ObjCClass("UIFont")
UITextField = ObjCClass("UITextField")
UIStackView = ObjCClass("UIStackView")
NSArray = ObjCClass("NSArray")

TOUCH_UP_INSIDE = 1 << 6
FLEX_WIDTH_HEIGHT = 2 | 16

# The dock's buttons, in the page's own order (#dock .dock-btn): the SF
# Symbol for each, and whether a phone has room for it.
DOCK = [
    ("house", "Home", True),
    ("slider.horizontal.3", "Options", True),
    ("clock.arrow.circlepath", "History", True),
    ("list.clipboard", "Guidelines", True),
    ("bubble.left.and.text.bubble.right", "Assistant", True),
    ("sparkles", "AI", True),       # its own tab (his ask, 20 Oct): the switch and the limit
    ("gearshape", "Settings", True),
    ("questionmark.circle", "Help", True),
]

PILL_H = 56       # the search pill and the dock
CHIP_H = 44       # the sources pill
GAP = 8
SIDE = 12


def _ui(cls, name):
    """A class-level value of UIKit's (a colour, a configuration): rubicon
    exposes some as properties and some as methods, by what the runtime
    declares, so take whichever this one is."""
    v = getattr(cls, name)
    return v() if callable(v) else v


def _sage():
    return UIColor.colorWithRed_green_blue_alpha_(0x6E / 255, 0x8B / 255, 0x6E / 255, 1.0)


def _glass_view():
    """A view of the system's glass; of its thin material before iOS 26."""
    try:
        UIGlassEffect = ObjCClass("UIGlassEffect")
        effect = UIGlassEffect.alloc().init()
        try:
            effect.interactive = True
        except Exception:
            pass
    except Exception:
        UIBlurEffect = ObjCClass("UIBlurEffect")
        effect = UIBlurEffect.effectWithStyle_(7)   # systemThinMaterial
    view = UIVisualEffectView.alloc().initWithEffect_(effect)
    try:
        UICornerConfiguration = ObjCClass("UICornerConfiguration")
        view.cornerConfiguration = UICornerConfiguration.capsuleConfiguration()
    except Exception:
        view.clipsToBounds = True
        view.layer.cornerRadius = CHIP_H / 2
    return view


class ChromeHandler(NSObject):
    """Receives the taps and the Return key; the chrome tells the shell."""

    chrome = objc_property(object, weak=True)

    @objc_method
    def dockTapped_(self, sender) -> None:
        if self.chrome is not None:
            self.chrome.on_dock(int(sender.tag))

    @objc_method
    def sourcesTapped_(self, sender) -> None:
        if self.chrome is not None:
            self.chrome.on_sources()

    @objc_method
    def searchTapped_(self, sender) -> None:
        if self.chrome is not None:
            self.chrome.on_search()

    @objc_method
    def closeTapped_(self, sender) -> None:
        if self.chrome is not None:
            self.chrome.on_close()

    @objc_method
    def textFieldShouldReturn_(self, field) -> bool:
        if self.chrome is not None:
            self.chrome.on_search()
        return True


class NativeChrome:
    def __init__(self, window, run_js, wide: bool):
        """window: the UIWindow; run_js: a callable taking a script for the page;
        wide: an iPad (room for the words under the dock's icons)."""
        self.window = window
        self.run_js = run_js
        self.wide = wide

        self.handler = ChromeHandler.alloc().init()
        self.handler.chrome = self

        # ── The search pill ──────────────────────────────────────────────
        self.search = _glass_view()
        content = self.search.contentView
        icon = UIImageView.alloc().initWithImage_(UIImage.systemImageNamed_("magnifyingglass"))
        icon.tintColor = _ui(UIColor, "secondaryLabelColor")
        icon.contentMode = 1   # scale aspect fit
        self.search_icon = icon
        content.addSubview_(icon)
        field = UITextField.alloc().init()
        field.placeholder = "Search the literature"
        field.font = UIFont.systemFontOfSize_(17)
        field.returnKeyType = 6            # Search
        field.autocorrectionType = 1       # no
        field.autocapitalizationType = 0   # none
        field.clearButtonMode = 1          # while editing
        field.delegate = self.handler
        self.field = field
        content.addSubview_(field)
        go = UIButton.buttonWithType_(1)
        try:
            UIButtonConfiguration = ObjCClass("UIButtonConfiguration")
            cfg = UIButtonConfiguration.filledButtonConfiguration()
            cfg.title = "Search"
            cfg.baseBackgroundColor = _sage()
            cfg.baseForegroundColor = _ui(UIColor, "whiteColor")
            cfg.cornerStyle = 4            # capsule
            go.configuration = cfg
        except Exception:
            go.setTitle_forState_("Search", 0)
            go.backgroundColor = _sage()
            go.layer.cornerRadius = 22
        go.tintColor = _ui(UIColor, "whiteColor")   # the title; a system button draws it in its tint
        go.addTarget_action_forControlEvents_(self.handler, SEL("searchTapped:"), TOUCH_UP_INSIDE)
        self.go = go
        content.addSubview_(go)

        # ── The sources pill ─────────────────────────────────────────────
        self.sources = _glass_view()
        chip = UIButton.buttonWithType_(1)
        chip.tintColor = _ui(UIColor, "labelColor")
        self._set_chip(chip, "PubMed")
        chip.addTarget_action_forControlEvents_(self.handler, SEL("sourcesTapped:"), TOUCH_UP_INSIDE)
        self.chip = chip
        self.sources.contentView.addSubview_(chip)

        # ── The dock ─────────────────────────────────────────────────────
        self.dock = _glass_view()
        self.dock_buttons = []
        symbol_cfg = UIImageSymbolConfiguration.configurationWithPointSize_weight_(20, 4)  # medium
        for i, (symbol, label, on_phone) in enumerate(DOCK):
            if not (on_phone or wide):
                continue
            b = UIButton.buttonWithType_(1)
            b.tag = i
            b.tintColor = _ui(UIColor, "labelColor")
            b.setImage_forState_(UIImage.systemImageNamed_(symbol), 0)
            b.setPreferredSymbolConfiguration_forImageInState_(symbol_cfg, 0)
            if wide:
                try:
                    UIButtonConfiguration = ObjCClass("UIButtonConfiguration")
                    cfg = UIButtonConfiguration.plainButtonConfiguration()
                    cfg.image = UIImage.systemImageNamed_(symbol)
                    cfg.imagePlacement = 1      # top
                    cfg.imagePadding = 3
                    cfg.baseForegroundColor = _ui(UIColor, "labelColor")
                    # The word in the caption size: at the button's own 15 pt
                    # "Guidelines" and "Assistant" broke with a hyphen on an
                    # iPad (19 Oct).
                    try:
                        NSAttributedString = ObjCClass("NSAttributedString")
                        cfg.attributedTitle = NSAttributedString.alloc().initWithString_attributes_(
                            label, {"NSFont": UIFont.systemFontOfSize_(11)})
                    except Exception:
                        cfg.title = label
                    b.configuration = cfg
                except Exception:
                    pass
            b.addTarget_action_forControlEvents_(self.handler, SEL("dockTapped:"), TOUCH_UP_INSIDE)
            self.dock_buttons.append(b)
        stack = UIStackView.alloc().initWithArrangedSubviews_(NSArray.arrayWithArray_(self.dock_buttons))
        stack.axis = 0           # horizontal
        stack.distribution = 1   # fill equally
        stack.autoresizingMask = FLEX_WIDTH_HEIGHT
        self.stack = stack
        self.dock.contentView.addSubview_(stack)

        # ── The close button: a glass circle with an X, shown while a panel,
        #    a sheet or the assistant has the screen (his ask, 19 Oct: as in
        #    the system's own apps). ──────────────────────────────────────
        self.close = _glass_view()
        x = UIButton.buttonWithType_(1)
        x.tintColor = _ui(UIColor, "labelColor")
        x.setImage_forState_(UIImage.systemImageNamed_("xmark"), 0)
        x.setPreferredSymbolConfiguration_forImageInState_(
            UIImageSymbolConfiguration.configurationWithPointSize_weight_(16, 6), 0)   # semibold
        x.addTarget_action_forControlEvents_(self.handler, SEL("closeTapped:"), TOUCH_UP_INSIDE)
        self.close_button = x
        self.close.contentView.addSubview_(x)
        self.is_open = False

        # ── The toast: a glass capsule sized to its words, with the system's
        #    symbol, above the sources pill (his ask, 21 Oct: the page's
        #    white bar was far from the app's style). Taps go through it.
        self.toast = _glass_view()
        self.toast.userInteractionEnabled = False
        self.toast.alpha = 0.0
        self.toast_icon = UIImageView.alloc().init()
        self.toast_icon.contentMode = 1
        self.toast.contentView.addSubview_(self.toast_icon)
        UILabel = ObjCClass("UILabel")
        self.toast_label = UILabel.alloc().init()
        self.toast_label.font = UIFont.systemFontOfSize_weight_(15, 0.23)   # medium
        self.toast_label.textColor = _ui(UIColor, "labelColor")
        self.toast_label.numberOfLines = 0
        self.toast.contentView.addSubview_(self.toast_label)
        self._toast_n = 0

        for v in (self.search, self.sources, self.dock, self.close, self.toast):
            window.addSubview_(v)
        self._apply_visibility()
        self.layout()

    # ── Layout ───────────────────────────────────────────────────────────
    def layout(self):
        b = self.window.bounds
        W, H = b.size.width, b.size.height
        ins = self.window.safeAreaInsets
        top, bottom = ins.top, ins.bottom
        # The sides too: an iPhone on its side has the Dynamic Island on one
        # (the sweep, 20 Oct: the pill ran under it in landscape).
        left, right = max(SIDE, ins.left), max(SIDE, ins.right)
        inner = W - left - right
        wide = W > 700

        # The search pill, under the status bar.
        self.search.frame = CGRectMake(left, top + GAP, inner, PILL_H)
        go_w = 96
        self.search_icon.frame = CGRectMake(20, (PILL_H - 20) / 2, 20, 20)
        self.field.frame = CGRectMake(50, 0, inner - 50 - go_w - 14, PILL_H)
        self.go.frame = CGRectMake(inner - go_w - 6, 6, go_w, PILL_H - 12)

        # The dock, above the home indicator; the sources pill above it.
        dock_w = min(inner, 760 if wide else inner)
        dock_y = H - bottom - GAP - PILL_H
        self.dock.frame = CGRectMake(left + (inner - dock_w) / 2, dock_y, dock_w, PILL_H)
        self.stack.frame = CGRectMake(4, 2, dock_w - 8, PILL_H - 4)

        # The close button, top right under the status bar.
        self.close.frame = CGRectMake(W - right - CHIP_H, top + GAP + (PILL_H - CHIP_H) / 2, CHIP_H, CHIP_H)
        self.close_button.frame = CGRectMake(0, 0, CHIP_H, CHIP_H)

        self.chip.sizeToFit()
        chip_w = max(120, self.chip.frame.size.width + 40)
        self.sources.frame = CGRectMake(left + (inner - chip_w) / 2, dock_y - GAP - CHIP_H, chip_w, CHIP_H)
        self.chip.frame = CGRectMake(0, 0, chip_w, CHIP_H)

        # The page lays out against the bars' true edges (--chrome-top: the
        # underside of the search pill; --chrome-bottom: from the screen's
        # bottom to the top of the sources pill), not against env() alone:
        # his phone drew the status line inside the pill while the simulator
        # did not (20 Oct), so the page's safe-area reading is not trusted
        # with the chrome's placement. Said again whenever the window lays
        # out, and once more when the page is up (shell.py).
        self.page_insets = (top + GAP + PILL_H, H - (dock_y - GAP - CHIP_H))
        self.tell_page_insets()

    def tell_page_insets(self):
        t, b = getattr(self, "page_insets", (0, 0))
        if not t:
            return
        self.run_js("(function(s){s.setProperty('--chrome-top','%dpx');s.setProperty('--chrome-bottom','%dpx');})"
                    "(document.documentElement.style)" % (round(t), round(b)))

    def _set_chip(self, chip, label):
        try:
            UIButtonConfiguration = ObjCClass("UIButtonConfiguration")
            cfg = UIButtonConfiguration.plainButtonConfiguration()
            cfg.image = UIImage.systemImageNamed_("square.stack.3d.up")
            cfg.title = label
            cfg.imagePadding = 8
            cfg.baseForegroundColor = _ui(UIColor, "labelColor")
            chip.configuration = cfg
        except Exception:
            chip.setTitle_forState_(label, 0)

    # ── From the page ────────────────────────────────────────────────────
    def set_sources_label(self, label: str):
        self._set_chip(self.chip, label or "Sources")
        self.layout()

    def set_query(self, text: str):
        if bool(self.field.isFirstResponder):
            return            # being typed in: the page's copy is the stale one
        if str(self.field.text or "") != text:
            self.field.text = text

    def set_dock_hidden(self, hidden):
        """The page's own hidden buttons (the Assistant while AI is off) are
        hidden here too; the stack shares the width among the rest."""
        hidden = set(hidden)
        if hidden == getattr(self, "_dock_hidden", set()):
            return
        self._dock_hidden = hidden
        for b in self.dock_buttons:
            b.setHidden_(int(b.tag) in hidden)
        self.stack.setNeedsLayout()
        print(f"chrome: dock buttons hidden {sorted(hidden)}")

    def set_dock_on(self, index: int):
        for b in self.dock_buttons:
            b.tintColor = _sage() if int(b.tag) == index else _ui(UIColor, "labelColor")

    def set_open(self, is_open: bool):
        """Something has the screen (a panel, a sheet, the assistant): the
        bars step aside and the close button takes their place."""
        if is_open != self.is_open:
            self.is_open = is_open
            self._apply_visibility()

    def _apply_visibility(self):
        shown = 0.0 if self.is_open else 1.0
        bars = (self.search, self.dock, self.sources)
        for v in bars:
            v.userInteractionEnabled = not self.is_open
        self.close.userInteractionEnabled = self.is_open

        def fade() -> None:
            for v in bars:
                v.alpha = shown
            self.close.alpha = 1.0 - shown

        # Over the screen's own rise (app.js slides it up in 0.48 s), on the
        # system's curve. Cut in and out, the bars popped (bumpy, 19 Oct).
        try:
            UIView.animateWithDuration(0.3 if self.is_open else 0.24, animations=Block(fade))
        except Exception as e:          # a rubicon that cannot make the block
            print(f"chrome: bars cut rather than faded ({e})")
            fade()

    def show_toast(self, text: str, kind: str, later, screen: bool = False):
        """A short notice: slides in a little from its edge and fades in, stays
        a moment (longer for more words), fades out the way it came.
        later(seconds, fn) schedules the fade; a newer toast takes over an
        older one's place and its timer. screen: a screen has the display (the
        page says so as it asks, a step ahead of set_open)."""
        self._toast_n += 1
        n = self._toast_n
        green = kind == "green"
        self.toast_icon.image = UIImage.systemImageNamed_("checkmark.circle.fill" if green else "info.circle")
        self.toast_icon.tintColor = _sage() if green else _ui(UIColor, "secondaryLabelColor")
        self.toast_icon.setPreferredSymbolConfiguration_(
            UIImageSymbolConfiguration.configurationWithPointSize_weight_(17, 5))   # semibold
        self.toast_label.text = text

        b = self.window.bounds
        W, H = b.size.width, b.size.height
        ins = self.window.safeAreaInsets
        left, right = max(SIDE, ins.left), max(SIDE, ins.right)
        icon, pad, gap = 22, 18, 10
        # On the X's row it stays clear of the X: as wide on both sides.
        room = W - 2 * (right + CHIP_H + GAP) if screen else W - left - right
        most = min(room, 520) - pad * 2 - icon - gap
        size = self.toast_label.sizeThatFits_(CGSizeMake(most, 1000))
        text_w, text_h = min(most, size.width), size.height
        h = max(CHIP_H, text_h + 22)
        w = pad + icon + gap + text_w + pad
        # WHERE THE SCREEN IS FREE (his rule, 21 Oct): with the bars up, at the
        # bottom, above the sources pill; with a screen up (the bars gone), on
        # the X's row at the top, which the screen leaves empty. Above the
        # pill while a screen was up it floated over the screen's fields; just
        # under the search pill it sat over the content (both his phone).
        if screen:
            x_mid = ins.top + GAP + PILL_H / 2          # the X's centre (layout)
            y = x_mid - h / 2
        else:
            y = self.sources.frame.origin.y - GAP - h
        enter = -14 if screen else 12                   # from its own edge
        x = (W - w) / 2
        self.toast_icon.frame = CGRectMake(pad, (h - icon) / 2, icon, icon)
        self.toast_label.frame = CGRectMake(pad + icon + gap, (h - text_h) / 2, text_w, text_h)
        self.window.bringSubviewToFront_(self.toast)
        if self.toast.alpha < 0.01:
            self.toast.frame = CGRectMake(x, y + enter, w, h)

        def rise() -> None:
            self.toast.frame = CGRectMake(x, y, w, h)
            self.toast.alpha = 1.0

        def sink() -> None:
            self.toast.frame = CGRectMake(x, y + enter * 0.7, w, h)
            self.toast.alpha = 0.0

        def hide():
            if n == self._toast_n:
                try:
                    UIView.animateWithDuration(0.3, animations=Block(sink))
                except Exception:
                    sink()

        try:
            UIView.animateWithDuration_delay_usingSpringWithDamping_initialSpringVelocity_options_animations_completion_(
                0.45, 0.0, 0.82, 0.0, 0, Block(rise), None)
        except Exception as e:
            print(f"chrome: toast cut rather than sprung ({e})")
            rise()
        later(min(6.0, 2.5 + len(text) / 40), hide)

    # ── To the page ──────────────────────────────────────────────────────
    def on_dock(self, index: int):
        self.run_js(f"(function(){{var b=document.querySelectorAll('#dock .dock-btn')[{index}]; if(b) b.click();}})()")

    def on_sources(self):
        self.run_js("(function(){var b=document.getElementById('dockSources'); if(b) b.click();})()")

    def on_close(self):
        self.run_js("if (window.__msCloseAll) window.__msCloseAll()")

    def on_search(self):
        import json
        q = json.dumps(str(self.field.text or ""))
        self.field.resignFirstResponder()
        self.run_js(f"(function(){{var i=document.getElementById('searchInput'); if(i){{i.value={q}; runSearch();}}}})()")
