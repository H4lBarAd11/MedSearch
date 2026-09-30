# MedSearch — the icon by the Windows clock.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""MedSearch's icon in the Windows notification area: statusbar.py's twin.

THE MAC'S MENU, ITEM FOR ITEM (appmenu.py): quick search, recent searches, the
default source, the window, Quit. Either mouse button opens it.

CLOSING THE WINDOW HIDES IT (his choice, 30 Sep, as on the Mac). MedSearch stays
by the clock, and the taskbar button goes with the window. With the PDF viewer
or a dialog open in the page, closing closes that instead. Quit in this menu
quits, and Windows signing out or shutting down is let through: a window that
refused would hold the shutdown up.

THE APP'S OWN ICON, ALWAYS THERE (his choices, 30 Sep): the sage tile rather
than a line drawing, and it stays while the window is in front, as Windows apps'
icons do.

WINFORMS, WHICH pywebview ALREADY RUNS MEDSEARCH'S WINDOWS ON: no new
dependency, and the menu and the quick-search box are Windows' own. Everything
that touches them runs on pywebview's GUI thread, reached through the main
window; the page is driven from another thread, because evaluate_js waits on
the GUI thread for its answer.
"""
from __future__ import annotations

import threading

import appmenu

_host = None   # the one Tray; module-level so nothing collects it


def menu_model(recents, current):
    """The menu as data, as statusbar.fill builds it: (label, action, value,
    checked) for an item, (label, [items]) for a submenu, None for a line."""
    rows = [("Search MedSearch…", "search", None, False), None]
    recents = list(recents)[:appmenu.RECENTS_SHOWN]
    if recents:
        rows.append(("Recent searches",
                     [(appmenu.short(q), "recent", q, False) for q in recents]))
    rows.append(("Default source",
                 [(label, "source", key, key == current) for key, label in appmenu.SOURCES]))
    rows += [None, ("Open MedSearch window", "open", None, False),
             None, ("Quit MedSearch", "quit", None, False)]
    return rows


# How a close was asked for: these must close, whatever the page has open.
_LET_THROUGH = ("WindowsShutDown", "TaskManagerClosing", "ApplicationExitCall")


class Tray:
    def __init__(self, window, *, icon_path, recent_searches, get_source, set_source):
        self.window = window                    # the pywebview main window
        self.icon_path = icon_path
        self.recent_searches = recent_searches  # () -> [query, ...], newest first
        self.get_source = get_source            # () -> source key
        self.save_source = set_source           # (key) -> None
        self.quitting = False                   # Quit chosen, or Windows ending
        self.notify = None

    # ── pywebview's GUI thread ──────────────────────────────────────────────
    def _gui(self, fn):
        """Run `fn` on the GUI thread, without waiting for it."""
        from System import Action
        form = self.window.native
        if form.InvokeRequired:
            form.BeginInvoke(Action(fn))
        else:
            fn()

    def build(self):
        """The icon and its menu. On the GUI thread."""
        import clr
        clr.AddReference("System.Windows.Forms")
        clr.AddReference("System.Drawing")
        import System.Windows.Forms as WinForms
        from System.Drawing import Icon

        self._wf = WinForms
        n = WinForms.NotifyIcon()
        try:
            n.Icon = Icon(str(self.icon_path), WinForms.SystemInformation.SmallIconSize)
        except Exception:
            n.Icon = self.window.native.Icon
        n.Text = "MedSearch"
        menu = WinForms.ContextMenuStrip()
        menu.Opening += lambda s, e: self.fill(menu)     # recents never stale
        self.fill(menu)
        n.ContextMenuStrip = menu
        n.MouseUp += self._clicked
        n.Visible = True
        self.notify, self.menu = n, menu
        self.window.native.FormClosing += self._form_closing

    def _clicked(self, sender, e):
        """A left click opens the menu too (a right click does on its own)."""
        if e.Button != self._wf.MouseButtons.Left:
            return
        try:
            import clr
            from System.Reflection import BindingFlags
            show = clr.GetClrType(self._wf.NotifyIcon).GetMethod(
                "ShowContextMenu", BindingFlags.Instance | BindingFlags.NonPublic)
            show.Invoke(self.notify, None)
        except Exception:
            self.show()

    def fill(self, menu):
        wf = self._wf
        menu.Items.Clear()

        def item(row, into):
            if row is None:
                into.Add(wf.ToolStripSeparator())
                return
            if isinstance(row[1], list):
                sub = wf.ToolStripMenuItem(row[0])
                for r in row[1]:
                    item(r, sub.DropDownItems)
                into.Add(sub)
                return
            label, action, value, checked = row
            mi = wf.ToolStripMenuItem(label)
            mi.Checked = bool(checked)
            mi.Click += lambda s, e, a=action, v=value: self._do(a, v)
            into.Add(mi)

        for row in menu_model(self.recent_searches(), self.get_source()):
            item(row, menu.Items)

    def _do(self, action, value):
        if action == "search":
            self.quick_search()
        elif action == "recent":
            self.run(str(value))
        elif action == "source":
            self.save_source(str(value))
        elif action == "open":
            self.show()
        elif action == "quit":
            self.quit()

    # ── the window ──────────────────────────────────────────────────────────
    def show(self):
        """Bring the window back from wherever it is: hidden by the clock,
        minimised, or merely behind something else. From any thread."""
        def do():
            form = self.window.native
            if form.WindowState == self._wf.FormWindowState.Minimized:
                form.WindowState = self._wf.FormWindowState.Normal
            form.Show()
            form.Activate()
            try:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(form.Handle.ToInt64())
            except Exception:
                pass
        self._gui(do)
        return True

    def hide(self):
        self._gui(lambda: self.window.native.Hide())

    def run(self, query, source=None):
        """Show the window and run the search in it, as the page's own Search does."""
        self.show()
        js = appmenu.search_js(query, source or self.get_source())
        threading.Thread(target=lambda: self.window.evaluate_js(js), daemon=True).start()

    def quick_search(self):
        """A small box of Windows' own: the search, and Search or Cancel."""
        wf = self._wf
        from System.Drawing import Size, SystemFonts
        box = wf.Form()
        box.Text = appmenu.QUICK_SEARCH_TITLE
        box.FormBorderStyle = wf.FormBorderStyle.FixedDialog
        box.MaximizeBox = box.MinimizeBox = False
        box.StartPosition = wf.FormStartPosition.CenterScreen
        box.TopMost = True
        box.Font = SystemFonts.MessageBoxFont
        box.AutoScaleMode = wf.AutoScaleMode.Font
        box.AutoSize = True
        box.AutoSizeMode = wf.AutoSizeMode.GrowAndShrink
        box.Padding = wf.Padding(12)

        column = wf.FlowLayoutPanel()
        column.FlowDirection = wf.FlowDirection.TopDown
        column.AutoSize = True
        column.WrapContents = False
        hint = wf.Label()
        hint.Text = appmenu.quick_search_hint(self.get_source())
        hint.AutoSize = True
        hint.MaximumSize = Size(360, 0)
        field = wf.TextBox()
        field.Width = 360
        buttons = wf.FlowLayoutPanel()
        buttons.FlowDirection = wf.FlowDirection.RightToLeft
        buttons.AutoSize = True
        buttons.Width = 360
        search, cancel = wf.Button(), wf.Button()
        search.Text, search.DialogResult = "Search", wf.DialogResult.OK
        cancel.Text, cancel.DialogResult = "Cancel", wf.DialogResult.Cancel
        buttons.Controls.Add(cancel)
        buttons.Controls.Add(search)
        for c in (hint, field, buttons):
            column.Controls.Add(c)
        box.Controls.Add(column)
        box.AcceptButton, box.CancelButton = search, cancel
        box.ActiveControl = field
        try:
            if box.ShowDialog() == wf.DialogResult.OK:
                query = str(field.Text or "").strip()
                if query:
                    self.run(query)
        finally:
            box.Dispose()

    # ── closing the window hides it; quitting still quits ──────────────────
    def closing(self):
        """pywebview's `closing` handler for the main window: False keeps it
        open (and hides it instead), anything else lets it close. Any other close
        is decided off the GUI thread, which evaluate_js needs free."""
        if self.quitting:
            print("  window closed: MedSearch is quitting")
            return True
        print("  window closed: hiding it by the clock (a dialog closes first)")
        threading.Thread(target=self._close_dialog_or_hide, daemon=True).start()
        return False

    def _close_dialog_or_hide(self):
        if not appmenu.page_closed_a_dialog(self.window):
            self.hide()

    def _form_closing(self, sender, args):
        """After pywebview's own handler, which asked `closing`: Windows ending
        the session, Task Manager and Quit are let through whatever it said."""
        reason = str(args.CloseReason)
        print(f"  close asked by {reason}; {'letting it through' if reason in _LET_THROUGH else 'kept'}")
        if reason in _LET_THROUGH:
            self.quitting = True
            args.Cancel = False

    def quit(self):
        print("  Quit chosen in the tray menu")
        self.quitting = True
        if self.notify is not None:
            self.notify.Visible = False          # or a ghost icon stays by the clock
            self.notify.Dispose()
        self._wf.Application.Exit()              # every window closes; `closing` agrees


def install(window, *, background=False, **kwargs):
    """Put the icon by the clock and make closing the window hide it. Call on
    the GUI thread, once the window exists. `background` is a start at login:
    the window is already hidden, so nothing more is needed for it."""
    global _host
    _host = Tray(window, **kwargs)
    _host.build()
    window.events.closing += _host.closing
    return _host
