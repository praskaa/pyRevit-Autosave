"""Shared session state for the engine and ribbon scripts."""
from System import AppDomain
from pyrevit import script

PREFIX = "praskaa.autosave."


def get(name):
    return AppDomain.CurrentDomain.GetData(PREFIX + name)


def put(name, value):
    AppDomain.CurrentDomain.SetData(PREFIX + name, value)


def enabled():
    return bool(get("enabled"))


def publish(status, detail):
    if status == get("status") and detail == get("detail"):
        return
    put("status", status)
    put("detail", detail)
    render = get("render")
    if render is not None:
        try:
            render.Invoke()
        except Exception as ex:
            script.get_logger().error("Could not update the AutoSave ribbon: %s", ex)


def refresh():
    if not enabled():
        publish("OFF", "Click to enable local AutoSave for this Revit session.")
    elif get("request") is None:
        publish("ON - Error", "AutoSave engine unavailable. Reload pyRevit.")
    else:
        publish("ON - Starting", "Waiting for Revit to run the AutoSave engine.")
        get("request").Invoke()
