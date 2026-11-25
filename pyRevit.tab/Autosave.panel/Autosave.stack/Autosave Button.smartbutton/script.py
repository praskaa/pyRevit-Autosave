from System import Action

from pyrevit.coreutils.ribbon import ICON_MEDIUM
from pyrevit.revit import ui

import autosave_state as state

__context__ = "zero-doc"
__title__ = "AutoSave"
__author__ = "Alex D'Aversa"


def __selfinit__(script_cmp, ui_button_cmp, __rvt__):
    on_icon = ui.resolve_icon_file(script_cmp.directory, "on.png")
    off_icon = ui.resolve_icon_file(script_cmp.directory, "off.png")
    # The compiled pyRevit loader passes a SmartButtonContext. Older
    # loaders pass a ribbon wrapper with the Python setters.
    push_button = getattr(ui_button_cmp, "ui_button", None)
    icon_state = [None]

    def render():
        status = state.get("status") or "OFF"
        is_on = status != "OFF"
        title = "AutoSave\n" + (status if is_on else "OFF - CLICK TO ENABLE")
        tooltip = state.get("detail") or "Local AutoSave."
        if not is_on:
            tooltip = "AutoSave is OFF. Click this button to enable it for this Revit session.\n\n" + tooltip
        if push_button is not None:
            push_button.ItemText = title
            push_button.ToolTip = tooltip
        else:
            ui_button_cmp.set_title(title)
            ui_button_cmp.set_tooltip(tooltip)
        if icon_state[0] != is_on:
            ui_button_cmp.set_icon(
                on_icon if is_on else off_icon, icon_size=ICON_MEDIUM
            )
            icon_state[0] = is_on

    state.put("render", Action(render))
    state.refresh()
    render()
    return True


if __name__ == "__main__":
    if __shiftclick__:
        from autosave_settings import set_interval
        set_interval()
    else:
        state.put("enabled", not state.enabled())
        state.refresh()
