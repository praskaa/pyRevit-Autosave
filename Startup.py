# -*- coding: utf-8 -*-
# Autosave engine (extension root startup.py).
# Replaces the view-activated, doc-opened and doc-saved hooks (remove them).
#
# How it works:
#   * ViewActivated only MARKS the moment (never saves inside the event).
#   * Idling does the save, 3-15 s after a view change, when the interval
#     is due. So a script that switches views and keeps working is never
#     interrupted: every new view change restarts the settle timer.
#   * Fallback: if the save is overdue (no view change for a long time),
#     save once the user has had no mouse/keyboard input for a while.
#   * A small click-through dot near the bottom-right of the Revit window
#     shows that autosave is ON (green) or ON but skipping the active
#     document (amber). It is hidden when autosave is OFF.
#
# Config, [autosave] section (all optional except the first four):
#   enabled, interval (s), include_workshared, include_cloud_models
#   view_settle (3 s), view_window (15 s), max_overdue (600 s),
#   idle_required (20 s), indicator (true), indicator_offset_x (16),
#   indicator_offset_y (44), indicator_opacity (0.4, range 0.1 - 1.0)
#
# TODO: [FEATURE] skip save while Revit is in sketch / in-place edit mode
# TODO: [FEATURE] confirm Idling frequency on a still screen (see log)
import time

import clr

clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
clr.AddReference("WindowsBase")

from System import AppDomain, EventHandler
from System.Diagnostics import Process
from System.Windows import (
    PresentationSource,
    ResizeMode,
    Visibility,
    Window,
    WindowStartupLocation,
    WindowStyle,
)
from System.Windows.Interop import WindowInteropHelper
from System.Windows.Media import Brushes, Color, SolidColorBrush
from System.Windows.Shapes import Ellipse

from pyrevit import HOST_APP, script
from pyrevit.userconfig import user_config

from Autodesk.Revit.UI.Events import IdlingEventArgs, ViewActivatedEventArgs

try:
    import ctypes
    _HAS_CTYPES = True
except Exception:
    _HAS_CTYPES = False

logger = script.get_logger()

KEY_IDLING = "praskaa.autosave.idling_handler"
KEY_VIEW = "praskaa.autosave.view_handler"
KEY_ENABLED = "praskaa.autosave.enabled"
KEY_WINDOW = "praskaa.autosave.indicator_window"

TICK_SECONDS = 1
CONFIG_REFRESH_SECONDS = 30
INDICATOR_SIZE = 10

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

_last_save = {}  # document path -> time of last save / baseline
_view_event = [0.0]  # time of the last view activation
_view_consumed = [True]  # True once that activation was used (or ignored)
_next_tick = [0.0]
_next_cfg = [0.0]
_ind = {"win": None, "mode": None, "rect": None, "broken": False}
_warned = {"idle": False}

if _HAS_CTYPES:
    class _LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]


# --- config -----------------------------------------------------------------
def _cfg(name, default):
    try:
        if user_config.autosave.has_option(name):
            return user_config.autosave.get_option(name)
    except Exception:
        pass
    return default


def _refresh_config():
    # The toggle button runs in another engine and saves the config file;
    # re-read it so this engine does not use a stale copy.
    try:
        reload_cfg = getattr(user_config, "reload", None)
        if reload_cfg:
            reload_cfg()
    except Exception as ex:
        logger.debug("autosave config reload failed: %s", ex)
    AppDomain.CurrentDomain.SetData(KEY_ENABLED, bool(_cfg("enabled", False)))


def _is_enabled():
    # KEY_ENABLED is set instantly by the toggle button (script.py) and
    # re-synced from the config file every CONFIG_REFRESH_SECONDS.
    flag = AppDomain.CurrentDomain.GetData(KEY_ENABLED)
    if flag is None:
        return bool(_cfg("enabled", False))
    return bool(flag)


# --- document rules ---------------------------------------------------------
def _is_cloud(doc):
    try:
        return bool(doc.IsModelInCloud)
    except Exception:
        return False


def _eligible(doc):
    if doc.IsFamilyDocument or doc.IsLinked or doc.IsDetached:
        return False
    if len(doc.PathName) == 0:
        return False
    if doc.IsWorkshared and not _cfg("include_workshared", False):
        return False
    if _is_cloud(doc) and not _cfg("include_cloud_models", False):
        return False
    return True


def _idle_seconds():
    """Seconds since the last mouse/keyboard input (system wide)."""
    if not _HAS_CTYPES:
        return None
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        tick = ctypes.windll.kernel32.GetTickCount()
        return ((tick - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except Exception:
        return None


# --- indicator --------------------------------------------------------------
def _revit_hwnd():
    return Process.GetCurrentProcess().MainWindowHandle


def _revit_rect():
    if not _HAS_CTYPES:
        return None
    rect = _RECT()
    handle = ctypes.c_void_p(_revit_hwnd().ToInt64())
    if not ctypes.windll.user32.GetWindowRect(handle, ctypes.byref(rect)):
        return None
    return (rect.left, rect.top, rect.right, rect.bottom)


def _make_click_through(hwnd):
    if not _HAS_CTYPES:
        return
    user32 = ctypes.windll.user32
    handle = ctypes.c_void_p(hwnd.ToInt64())
    style = user32.GetWindowLongW(handle, GWL_EXSTYLE)
    user32.SetWindowLongW(
        handle,
        GWL_EXSTYLE,
        style | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
    )


def _dpi_scale(win):
    try:
        source = PresentationSource.FromVisual(win)
        return source.CompositionTarget.TransformToDevice.M11
    except Exception:
        return 1.0


def _close_window(win):
    try:
        win.Close()
    except Exception as ex:
        logger.debug("indicator close failed: %s", ex)


def _create_indicator():
    win = Window()
    win.WindowStyle = getattr(WindowStyle, "None")  # 'None' is a keyword
    win.ResizeMode = ResizeMode.NoResize
    win.AllowsTransparency = True
    win.Background = Brushes.Transparent
    win.ShowInTaskbar = False
    win.ShowActivated = False
    win.Topmost = False
    win.Focusable = False
    win.WindowStartupLocation = WindowStartupLocation.Manual
    win.Width = INDICATOR_SIZE
    win.Height = INDICATOR_SIZE

    dot = Ellipse()
    dot.Width = INDICATOR_SIZE
    dot.Height = INDICATOR_SIZE
    dot.Stroke = Brushes.White
    dot.StrokeThickness = 1
    dot.Opacity = min(1.0, max(0.1, float(_cfg("indicator_opacity", 0.4))))
    win.Content = dot

    helper = WindowInteropHelper(win)
    helper.Owner = _revit_hwnd()  # shows only above Revit, not other apps
    _make_click_through(helper.EnsureHandle())
    win.Show()
    AppDomain.CurrentDomain.SetData(KEY_WINDOW, win)
    return win


def _position_indicator(win):
    rect = _revit_rect()
    if rect is None or rect == _ind["rect"] or rect[0] <= -30000:
        return
    _ind["rect"] = rect
    scale = _dpi_scale(win)
    off_x = float(_cfg("indicator_offset_x", 16))
    off_y = float(_cfg("indicator_offset_y", 44))
    win.Left = rect[2] / scale - off_x - INDICATOR_SIZE
    win.Top = rect[3] / scale - off_y - INDICATOR_SIZE


def _set_indicator(mode):
    """mode: None (hidden), 'active' (green) or 'skipped' (amber)."""
    if _ind["broken"]:
        return
    try:
        win = _ind["win"]
        if mode is None or not _HAS_CTYPES:
            if win is not None and win.Visibility != Visibility.Collapsed:
                win.Visibility = Visibility.Collapsed
            _ind["mode"] = None
            return
        if win is None:
            win = _create_indicator()
            _ind["win"] = win
            _ind["rect"] = None
        if win.Visibility != Visibility.Visible:
            win.Visibility = Visibility.Visible
        if mode != _ind["mode"]:
            if mode == "active":
                color = Color.FromRgb(0x2E, 0xCC, 0x71)
            else:
                color = Color.FromRgb(0xF1, 0xC4, 0x0F)
            win.Content.Fill = SolidColorBrush(color)
            _ind["mode"] = mode
        _position_indicator(win)
    except Exception as ex:
        _ind["broken"] = True
        logger.error("Autosave indicator disabled: %s", ex)


# --- autosave ---------------------------------------------------------------
def _do_save(doc, key, reason):
    logger.debug("autosave start (%s): %s", reason, doc.Title)
    started = time.time()
    try:
        doc.Save()
        logger.info(
            "Autosaved %s via %s in %.1fs",
            doc.Title, reason, time.time() - started,
        )
    except Exception as ex:
        logger.warning("Autosave failed for %s: %s", doc.Title, ex)
    _last_save[key] = time.time()


def _tick(uiapp, now):
    if now >= _next_cfg[0]:
        _next_cfg[0] = now + CONFIG_REFRESH_SECONDS
        _refresh_config()

    enabled = _is_enabled()
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document if uidoc is not None else None
    eligible = enabled and doc is not None and _eligible(doc)

    if enabled and bool(_cfg("indicator", True)):
        _set_indicator("active" if eligible else "skipped")
    else:
        _set_indicator(None)
    if not eligible:
        return

    key = doc.PathName
    last = _last_save.get(key)
    if last is None:
        # first sighting: baseline only, never save a freshly opened doc
        _last_save[key] = now
        return

    elapsed = now - last
    interval = float(_cfg("interval", 900))
    if elapsed < interval:
        return
    if not doc.IsModified:
        _last_save[key] = now
        return
    if doc.IsModifiable or doc.IsReadOnly:
        # transaction open or read-only: retry on a later tick
        return

    settle = float(_cfg("view_settle", 3))
    window = float(_cfg("view_window", 15))
    view_age = now - _view_event[0]
    via_view = (not _view_consumed[0]) and settle <= view_age <= window

    via_idle = False
    if elapsed >= interval + float(_cfg("max_overdue", 600)):
        idle = _idle_seconds()
        if idle is None and not _warned["idle"]:
            _warned["idle"] = True
            logger.warning("autosave: cannot read input idle time (ctypes)")
        via_idle = idle is not None and idle >= float(
            _cfg("idle_required", 20)
        )

    if via_view:
        _view_consumed[0] = True
        _do_save(doc, key, "view change")
    elif via_idle:
        _do_save(doc, key, "idle")


def _on_idling(sender, args):
    now = time.time()
    if now < _next_tick[0]:
        return
    _next_tick[0] = now + TICK_SECONDS
    try:
        _tick(sender, now)
    except Exception as ex:
        # a background handler must never bring down the session
        logger.error("Autosave idling error: %s", ex)


def _on_view_activated(sender, args):
    # Mark only. Saving inside this event could break a running script.
    _view_event[0] = time.time()
    _view_consumed[0] = False


# --- registration -----------------------------------------------------------
def _register():
    uiapp = HOST_APP.uiapp
    domain = AppDomain.CurrentDomain

    # a pyRevit reload re-runs this file: drop previous handlers and dot
    old_idling = domain.GetData(KEY_IDLING)
    if old_idling is not None:
        try:
            uiapp.Idling -= old_idling
        except Exception as ex:
            logger.debug("could not remove old idling handler: %s", ex)
    old_view = domain.GetData(KEY_VIEW)
    if old_view is not None:
        try:
            uiapp.ViewActivated -= old_view
        except Exception as ex:
            logger.debug("could not remove old view handler: %s", ex)
    old_win = domain.GetData(KEY_WINDOW)
    if old_win is not None:
        _close_window(old_win)
        domain.SetData(KEY_WINDOW, None)

    idling = EventHandler[IdlingEventArgs](_on_idling)
    view = EventHandler[ViewActivatedEventArgs](_on_view_activated)
    uiapp.Idling += idling
    uiapp.ViewActivated += view
    # keep references so the delegates are not garbage collected
    domain.SetData(KEY_IDLING, idling)
    domain.SetData(KEY_VIEW, view)


try:
    _register()
except Exception as ex:
    logger.error("Autosave handler registration failed: %s", ex)