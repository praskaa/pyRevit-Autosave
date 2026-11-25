# Ask whether to enable the session-only AutoSave when a document is opened.
from datetime import datetime

from pyrevit import forms, script

import autosave_state as state


logger = script.get_logger()


hour = datetime.now().hour
if 5 <= hour < 12:
    greeting = "good morning"
elif 12 <= hour < 17:
    greeting = "good arvo"
else:
    greeting = "good evening"

if not state.enabled():
    enable = forms.alert(
        "Hi Pras, {}!\n\nAutoSave is currently off. Would you like to turn it on for this Revit session?".format(greeting),
        title="AutoSave is off",
        ok=False,
        yes=True,
        no=True,
        warn_icon=False,
    )
    if enable:
        state.put("enabled", True)
        if state.get("request") is None:
            state.refresh()
        else:
            state.publish(
                "ON - Starting",
                "Starting AutoSave after the document-open reminder.",
            )
        logger.info("AutoSave enabled from the document-open reminder.")