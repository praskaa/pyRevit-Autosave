# -*- coding: utf-8 -*-
"""Diagnostik & tes Save untuk pyRevit-Autosave. Jalankan di dokumen target."""
import time
from System import AppDomain
from pyrevit import HOST_APP, script
from pyrevit.userconfig import user_config

logger = script.get_logger()
out = script.get_output()
out.print_md("## Autosave Save Diagnostic")

doc = HOST_APP.doc
uidoc = HOST_APP.uidoc

# --- config/runtime ---
try:
    reload_cfg = getattr(user_config, "reload", None)
    if reload_cfg:
        reload_cfg()
except Exception:
    pass

cfg_enabled = None
cfg_interval = None
try:
    if user_config.has_section("autosave"):
        if user_config.autosave.has_option("enabled"):
            cfg_enabled = user_config.autosave.get_option("enabled")
        if user_config.autosave.has_option("interval"):
            cfg_interval = user_config.autosave.get_option("interval")
except Exception as ex:
    out.print_md("**Config read error:** `{}`".format(ex))

rt_enabled = AppDomain.CurrentDomain.GetData("praskaa.autosave.enabled")
has_idling = AppDomain.CurrentDomain.GetData("praskaa.autosave.idling_handler") is not None
has_view = AppDomain.CurrentDomain.GetData("praskaa.autosave.view_handler") is not None

rows = [
    ["Item", "Value"],
    ["config.autosave.enabled", cfg_enabled],
    ["config.autosave.interval (sec)", cfg_interval],
    ["AppDomain runtime enabled", rt_enabled],
    ["Idling handler registered", has_idling],
    ["ViewActivated handler registered", has_view],
]
out.print_table(table_data=rows[1:], columns=rows[0], title="Runtime/Config")

if doc is None:
    out.print_md("**No active document.**")
    script.exit()

is_cloud = False
try:
    is_cloud = bool(doc.IsModelInCloud)
except Exception:
    pass

rows = [
    ["Item", "Value"],
    ["Title", doc.Title],
    ["PathName", doc.PathName],
    ["IsModified", doc.IsModified],
    ["IsModifiable (txn open)", doc.IsModifiable],
    ["IsReadOnly", doc.IsReadOnly],
    ["IsWorkshared", doc.IsWorkshared],
    ["IsModelInCloud", is_cloud],
    ["IsFamilyDocument", doc.IsFamilyDocument],
    ["IsLinked", doc.IsLinked],
    ["IsDetached", getattr(doc, "IsDetached", "n/a")],
]
out.print_table(table_data=rows[1:], columns=rows[0], title="Active Document")

# Eligibility mirroring Startup._eligible defaults
if not user_config.autosave.has_option("include_workshared"):
    inc_ws = False
else:
    inc_ws = bool(user_config.autosave.get_option("include_workshared"))
if not user_config.autosave.has_option("include_cloud_models"):
    inc_cloud = False
else:
    inc_cloud = bool(user_config.autosave.get_option("include_cloud_models"))

eligible = True
reasons = []
if doc.IsFamilyDocument or doc.IsLinked or getattr(doc, "IsDetached", False):
    eligible = False; reasons.append("family/linked/detached")
if len(doc.PathName) == 0:
    eligible = False; reasons.append("unsaved (empty PathName)")
if doc.IsWorkshared and not inc_ws:
    eligible = False; reasons.append("workshared excluded (include_workshared=false)")
if is_cloud and not inc_cloud:
    eligible = False; reasons.append("cloud excluded (include_cloud_models=false)")
out.print_md("**Eligible by autosave rules:** {} {}".format(
    eligible, "" if eligible else "({})".format(", ".join(reasons))))

# --- optional save test ---
# Amankan: hanya untuk file-based, non-workshared, punya path. Untuk workshared/cloud
# perilaku berbeda (sering perlu SynchronizeWithCentral), jadi kita tolak di tes ini.
if not doc.PathName:
    out.print_md("> Skip test save: dokumen belum punya path. Simpan manual sekali dulu.")
    script.exit()
if doc.IsWorkshared or is_cloud:
    out.print_md("> Skip test save: workshared/cloud butuh alur sync khusus; tes paksa `Save()` dihindari.")
    script.exit()
if doc.IsModifiable:
    out.print_md("> Skip test save: ada transaksi aktif (IsModifiable=True). Tutup command/transaksi lalu coba lagi.")
    script.exit()
if doc.IsReadOnly:
    out.print_md("> Skip test save: dokumen read-only.")
    script.exit()

from pyrevit import forms
if not forms.alert(
    "Tes akan memanggil doc.Save() pada dokumen aktif.\n"
    "Pastikan ini file lokal non-workshared yang aman untuk disave.\nLanjut?",
    title="Test Save",
    yes=True, no=True):
    script.exit()

t0 = time.time()
try:
    doc.Save()
    out.print_md("**doc.Save() OK** dalam {:.2f}s".format(time.time() - t0))
except Exception as ex:
    logger.warning("doc.Save() failed: %s", ex)
    out.print_md("**doc.Save() FAILED:** `{}`".format(ex))