# Updates the autosave baseline after ANY save (manual or autosave), so the
# autosave interval restarts from the most recent save.
#
# PATCH NOTES:
#   1. hash() replaced with deterministic hashlib.md5 (same reason as others).
#   2. Added logging instead of silent failure.
from System.Collections.Generic import *
from Autodesk.Revit.DB import *
from pyrevit import revit, DB, UI
from pyrevit import script
from pyrevit import forms
from pyrevit import EXEC_PARAMS
import time
import os
import hashlib

logger = script.get_logger()

try:
    doc = __eventargs__.Document
    title = doc.Title

    digest = hashlib.md5(doc.PathName.encode("utf-8")).hexdigest()[:10]
    savestatus_datafile = os.path.join(
        os.path.expandvars("%userprofile%\\AppData\\Roaming\\pyRevit\\Cache"),
        "{}_{}_savestatus.txt".format(title, digest),
    )

    with open(savestatus_datafile, "w") as f:
        f.write("{}|{}".format(title, time.time()))
except Exception as ex:
    logger.error("doc-saved: could not update save status: %s", ex)