# Records a baseline timestamp when a document is opened, so the autosave
# hook never saves a freshly opened document immediately.
#
# PATCH NOTES:
#   1. Fixed missing 'import sys' (the except path raised NameError instead).
#   2. hash() replaced with deterministic hashlib.md5 (see view-activated.py).
#   3. I/O wrapped with logging instead of bare crash.
from System.Collections.Generic import *
from Autodesk.Revit.DB import *
from pyrevit import revit, DB, UI
from pyrevit import script
from pyrevit import forms
from pyrevit import EXEC_PARAMS, HOST_APP
import time
import os
import sys
import hashlib

logger = script.get_logger()

doc = __eventargs__.Document
try:
    title = doc.Title
except Exception as ex:
    logger.error("doc-opened: could not read document title: %s", ex)
    sys.exit(1)

digest = hashlib.md5(doc.PathName.encode("utf-8")).hexdigest()[:10]
savestatus_datafile = os.path.join(
    os.path.expandvars("%userprofile%\\AppData\\Roaming\\pyRevit\\Cache"),
    "{}_{}_savestatus.txt".format(title, digest),
)

try:
    with open(savestatus_datafile, "w") as f:
        f.write("{}|{}".format(title, time.time()))
except Exception as ex:
    logger.error("doc-opened: could not write save status: %s", ex)