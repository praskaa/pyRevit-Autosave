from pyrevit import forms
from pyrevit.userconfig import user_config

import autosave_state as state


def option(name, default):
    if user_config.has_section("autosave"):
        section = user_config.autosave
        if section.has_option(name):
            return section.get_option(name)
    return default


def set_interval():
    minutes = forms.GetValueWindow.show(
        None,
        value_type="slider",
        default=float(option("interval", 900)) / 60,
        prompt="Set AutoSave interval in minutes:",
        title="AutoSave Interval",
        min=5,
        max=240,
    )
    if minutes is not None:
        if not user_config.has_section("autosave"):
            user_config.add_section("autosave")
        seconds = int(minutes * 60)
        user_config.autosave.interval = seconds
        user_config.save_changes()
        state.put("interval", seconds)
