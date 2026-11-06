# Ensures the autosave config section/options exist at Revit startup and
# cleans up orphaned save-status cache files.
#
# PATCH NOTES:
#   1. Added cleanup of *_savestatus.txt files older than 30 days. This
#      removes orphans left by the old non-deterministic hash() naming and
#      prevents unbounded growth of the pyRevit Cache folder. Worst case,
#      a cleaned document simply re-baselines without an immediate save.
from System.Collections.Generic import *
from pyrevit import revit, DB, UI
from pyrevit import script
from pyrevit import forms
from pyrevit import EXEC_PARAMS, HOST_APP
from pyrevit.userconfig import user_config
import time
import os

logger = script.get_logger()

if user_config.has_section("autosave"):
    if not user_config.autosave.has_option("interval"):
        user_config.autosave.interval = 900
    if not user_config.autosave.has_option("enabled"):
        user_config.autosave.enabled = False
    user_config.save_changes()
else:
    user_config.add_section("autosave")
    user_config.autosave.interval = 900
    user_config.autosave.enabled = False
    user_config.save_changes()

# --- cleanup of stale save-status files ---------------------------------
MAX_AGE_DAYS = 30
try:
    cache_dir = os.path.expandvars(
        "%userprofile%\\AppData\\Roaming\\pyRevit\\Cache"
    )
    now = time.time()
    for name in os.listdir(cache_dir):
        if name.endswith("_savestatus.txt"):
            path = os.path.join(cache_dir, name)
            try:
                if now - os.stat(path).st_mtime > MAX_AGE_DAYS * 86400:
                    os.remove(path)
                    logger.debug("cleaned stale save status: %s", name)
            except Exception:
                pass
except Exception as ex:
    logger.error("autosave cache cleanup failed: %s", ex)