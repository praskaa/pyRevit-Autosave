# -*- coding: utf-8 -*-
"""Run local saves in a Revit API context and report their outcomes."""
import os
import time

import clr
clr.AddReference("WindowsBase")
from System import Action, EventHandler, TimeSpan
from System.Windows.Threading import DispatcherTimer

from Autodesk.Revit.DB import BasicFileInfo, ModelPathUtils
from Autodesk.Revit.DB.Events import DocumentSavedEventArgs, RevitAPIEventStatus
from Autodesk.Revit.UI import (
    ExternalEvent, ExternalEventRequest, IExternalEventHandler,
    PostableCommand, RevitCommandId,
)
from Autodesk.Revit.UI.Events import ViewActivatedEventArgs
from pyrevit import HOST_APP, script
import autosave_state as state
from autosave_settings import option

logger = script.get_logger()
RETRY_SECONDS = 30
CONFIRM_SECONDS = 30

try:
    import ctypes
except ImportError:
    ctypes = None

if ctypes is not None:
    class LastInputInfo(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds():
    if ctypes is None:
        return 0
    info = LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    try:
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            tick = ctypes.windll.kernel32.GetTickCount()
            return ((tick - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except (AttributeError, OSError):
        pass
    return 0


def document_target(doc):
    """Return (identity, save kind, skip reason)."""
    if doc is None:
        return None, None, "No active document."
    if doc.IsLinked or getattr(doc, "IsDetached", False) or doc.IsReadOnly:
        return None, None, "Linked, detached, or read-only document."
    if getattr(doc, "IsModelInCloud", False):
        if not doc.IsWorkshared:
            return None, None, "This cloud model has no workshared local copy."
        model_path = doc.GetCloudModelPath()
        key = ("cloud", str(model_path.GetProjectGUID()),
               str(model_path.GetModelGUID()))
        return key, "cloud", None
    path = doc.PathName
    if not path:
        return None, None, "Save this document manually first."
    if not os.path.isabs(path):
        return None, None, "No writable file path."
    key = ("file", os.path.normcase(os.path.normpath(path)))
    return key, "workshared" if doc.IsWorkshared else "file", None


def verify_local_workshared(doc):
    """Require a recognized local file before calling Document.Save."""
    path = doc.PathName
    central = doc.GetWorksharingCentralModelPath()
    if central is not None:
        central_path = ModelPathUtils.ConvertModelPathToUserVisiblePath(central)
        if os.path.normcase(os.path.normpath(central_path)) == os.path.normcase(
                os.path.normpath(path)):
            return False
    info = BasicFileInfo.Extract(path)
    try:
        return info.IsLocal and not info.IsCentral
    finally:
        info.Dispose()


class SaveRecord(object):
    def __init__(self, doc, now):
        self.doc = doc
        self.baseline = now
        self.confirmed = None
        self.error = None
        self.retry_after = 0
        self.local_copy = None

    def saved(self, now):
        self.baseline = self.confirmed = now
        self.error = None
        self.retry_after = 0

    def fail(self, now, message):
        self.error = message
        self.retry_after = now + RETRY_SECONDS
        logger.warning("AutoSave: %s", message)


class AutosaveEngine(IExternalEventHandler):
    def __init__(self):
        self.records = {}
        self.pending = None
        self.was_enabled = False
        self.view_time = None
        self.view_used = False
        self.interval = float(option("interval", 900))
        self.view_settle = float(option("view_settle", 3))
        self.view_window = float(option("view_window", 15))
        self.max_overdue = float(option("max_overdue", 600))
        self.idle_required = float(option("idle_required", 20))

    def GetName(self):
        return "pyRevit local AutoSave"

    def Execute(self, uiapp):
        try:
            self.tick(uiapp, time.time())
        except Exception as ex:
            logger.error("AutoSave engine error: %s", ex)
            state.publish("ON - Error", str(ex))

    def view_activated(self, sender, args):
        self.view_time = time.time()
        self.view_used = False

    def document_saved(self, sender, args):
        if self.pending is None:
            return
        record, _ = self.pending
        if not record.doc.Equals(args.Document):
            return
        self.pending = None
        now = time.time()
        if args.Status == RevitAPIEventStatus.Succeeded:
            record.saved(now)
        else:
            record.fail(now, "Revit reported Save status: {}.".format(args.Status))

    def report(self, status, message, record=None):
        if record is not None:
            confirmed = record.confirmed
            last = (time.strftime("%H:%M:%S", time.localtime(confirmed))
                    if confirmed is not None else "none this session")
            message = "{}\nLast confirmed AutoSave: {}".format(message, last)
        state.publish(status, message)

    def tick(self, uiapp, now):
        if self.pending is not None and now >= self.pending[1]:
            self.pending[0].fail(now, "Revit did not confirm the local save.")
            self.pending = None

        if not state.enabled():
            self.was_enabled = False
            state.refresh()
            return
        self.was_enabled = True
        interval = max(1, float(state.get("interval") or self.interval))

        self.records = {key: record for key, record in self.records.items()
                        if record.doc.IsValidObject}
        uidoc = uiapp.ActiveUIDocument
        doc = uidoc.Document if uidoc is not None else None
        key, kind, skip = document_target(doc)
        if skip:
            self.report("ON - Skipped", skip)
            return

        record = self.records.get(key)
        if record is None or not record.doc.Equals(doc):
            record = self.records[key] = SaveRecord(doc, now)
        if self.pending is not None:
            self.report("ON - Saving", "Waiting for Revit to confirm Save.", record)
            return

        if kind == "workshared":
            if record.local_copy is None:
                record.local_copy = verify_local_workshared(doc)
            if not record.local_copy:
                self.report("ON - Skipped", "Open a local copy of the central model.", record)
                return

        if record.error:
            self.report("ON - Error", record.error, record)
            if now < record.retry_after or not doc.IsModified:
                return
        elif not doc.IsModified:
            if record.confirmed is None:
                self.report("ON - Ready", "No pending edits in the active document.", record)
            else:
                self.report("ON - Saved", "Local Save completed.", record)
            return
        elif doc.IsModifiable:
            self.report("ON - Waiting", "Waiting for the active transaction to finish.", record)
            return
        elif now - record.baseline < interval:
            self.report("ON - Waiting", "Waiting for the AutoSave interval.", record)
            return

        if doc.IsModifiable:
            return
        view_age = now - self.view_time if self.view_time is not None else -1
        after_view = not self.view_used and self.view_settle <= view_age <= self.view_window
        after_idle = (now - record.baseline >= interval + self.max_overdue
                      and idle_seconds() >= self.idle_required)
        if not (after_view or after_idle):
            if not record.error:
                self.report("ON - Waiting", "Save due. Switch views or wait for Revit to idle.", record)
            return

        try:
            if kind == "cloud":
                # The ordinary Revit Save command is Ctrl+S. On a cloud
                # workshared model it saves the local working copy.
                command = RevitCommandId.LookupPostableCommandId(PostableCommand.Save)
                if not uiapp.CanPostCommand(command):
                    self.report("ON - Waiting", "Revit Save is temporarily unavailable.", record)
                    return
                uiapp.PostCommand(command)
                self.pending = (record, now + CONFIRM_SECONDS)
                self.view_used = True
                self.report("ON - Saving", "Waiting for Revit to confirm local Save.", record)
            else:
                if kind == "workshared" and not verify_local_workshared(doc):
                    record.local_copy = False
                    self.report("ON - Skipped", "Open a local copy of the central model.", record)
                    return
                self.view_used = True
                self.pending = (record, now + CONFIRM_SECONDS)
                self.report("ON - Saving", "Saving the working copy.", record)
                doc.Save()
                if self.pending is not None:
                    self.pending = None
                    record.fail(time.time(), "Revit did not confirm the local save.")
                if record.error:
                    self.report("ON - Error", record.error, record)
                else:
                    self.report("ON - Saved", "Local Save completed.", record)
        except Exception as ex:
            self.pending = None
            self.view_used = True
            record.fail(time.time(), str(ex))
            self.report("ON - Error", record.error, record)


def register():
    previous = state.get("stop")
    state.put("request", None)
    state.put("stop", None)
    if previous is not None:
        previous.Invoke()

    uiapp = HOST_APP.uiapp
    app = uiapp.Application
    engine = AutosaveEngine()
    request = ExternalEvent.Create(engine)
    timer = DispatcherTimer()
    timer.Interval = TimeSpan.FromSeconds(1)
    saved = EventHandler[DocumentSavedEventArgs](engine.document_saved)
    view = EventHandler[ViewActivatedEventArgs](engine.view_activated)

    def raise_event():
        try:
            result = request.Raise()
            if result not in (ExternalEventRequest.Accepted, ExternalEventRequest.Pending):
                raise RuntimeError(str(result))
        except Exception as ex:
            if state.enabled():
                state.publish("ON - Error", "Could not request AutoSave: {}".format(ex))

    def on_timer(sender, args):
        if state.enabled() or engine.was_enabled or engine.pending is not None:
            raise_event()

    def stop():
        timer.Stop()
        timer.Tick -= tick
        uiapp.ViewActivated -= view
        app.DocumentSaved -= saved
        request.Dispose()

    tick = EventHandler(on_timer)
    app.DocumentSaved += saved
    try:
        uiapp.ViewActivated += view
        try:
            timer.Tick += tick
            timer.Start()
        except Exception:
            uiapp.ViewActivated -= view
            raise
    except Exception:
        app.DocumentSaved -= saved
        request.Dispose()
        raise
    state.put("stop", Action(stop))
    state.put("request", Action(raise_event))
    state.refresh()


try:
    register()
except Exception as ex:
    logger.error("AutoSave registration failed: %s", ex)
    state.put("request", None)
    state.refresh()
