from pyrevit import script

import autosave_state as state

__context__ = "zero-doc"
__title__ = "AutoSave Status"

out = script.get_output()
out.print_md("## AutoSave status")
print(state.get("status") or "OFF")
print(state.get("detail") or "Click AutoSave to enable it for this Revit session.")
