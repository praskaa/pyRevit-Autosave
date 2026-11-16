                    doc.Title, reason, time.time() - started)
    except Exception as ex:
        logger.warning("Autosave failed for %s: %s", doc.Title, ex)


def _tick(uiapp, now):
    if now >= _next_cfg[0]:
        _next_cfg[0] = now + CONFIG_REFRESH_SECONDS
        _refresh_config()

    enabled = _is_enabled()
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document if uidoc is not None else None
    reason = _skip_reason(doc) if (enabled and doc is not None) else None
    eligible = enabled and doc is not None and reason is None

    if _startup_notice[0]:
        _startup_notice[0] = False
        if enabled:
            minutes = int(float(_cfg("interval", 900)) / 60)
            _notify("Autosave is ON (every {} min).".format(minutes))
    if (
        enabled
        and reason is not None
        and reason[0] in NOTIFY_CODES
        and doc.Title not in _notified_skip
    ):
        _notified_skip.add(doc.Title)
        _notify(
            "Autosave is ON, but '{}' is skipped: {}.".format(
                doc.Title, reason[1]
            )
        )

    if enabled and bool(_cfg("indicator", True)):
        _set_indicator("active" if eligible else "skipped")
    else:
        _set_indicator(None)
    if not eligible:
        return

    key = doc.PathName
    last = _last_save.get(key)
    if last is None:
        # first sighting: baseline only, never save a freshly opened doc
        _last_save[key] = now
        return

    elapsed = now - last
    interval = float(_cfg("interval", 900))
    if elapsed < interval:
        return
    if not doc.IsModified:
        _last_save[key] = now
        return
    if doc.IsModifiable or doc.IsReadOnly:
        # transaction open or read-only: retry on a later tick
        return

    settle = float(_cfg("view_settle", 3))
    window = float(_cfg("view_window", 15))
    view_age = now - _view_event[0]
    via_view = (not _view_consumed[0]) and settle <= view_age <= window

    via_idle = False
    if elapsed >= interval + float(_cfg("max_overdue", 600)):
        idle = _idle_seconds()
        if idle is None and not _warned["idle"]:
            _warned["idle"] = True
            logger.warning("autosave: cannot read input idle time (ctypes)")
        via_idle = idle is not None and idle >= float(
            _cfg("idle_required", 20)
        )

    if via_view:
        _view_consumed[0] = True
        _do_save(doc, key, "view change")
    elif via_idle:
        _do_save(doc, key, "idle")


def _on_idling(sender, args):
    now = time.time()
    if now < _next_tick[0]:
        return
    _next_tick[0] = now + TICK_SECONDS
    try:
        _tick(sender, now)
    except Exception as ex:
        # a background handler must never bring down the session
        logger.error("Autosave idling error: %s", ex)


def _on_view_activated(sender, args):
    # Mark only. Saving inside this event could break a running script.
    _view_event[0] = time.time()
    _view_consumed[0] = False


# --- registration -----------------------------------------------------------
def _register():
    uiapp = HOST_APP.uiapp
    domain = AppDomain.CurrentDomain

    # a pyRevit reload re-runs this file: drop previous handlers and dot
    old_idling = domain.GetData(KEY_IDLING)
    if old_idling is not None:
        try:
            uiapp.Idling -= old_idling
        except Exception as ex:
            logger.debug("could not remove old idling handler: %s", ex)
    old_view = domain.GetData(KEY_VIEW)
    if old_view is not None:
        try:
            uiapp.ViewActivated -= old_view
        except Exception as ex:
            logger.debug("could not remove old view handler: %s", ex)
    old_win = domain.GetData(KEY_WINDOW)
    if old_win is not None:
        _close_window(old_win)
        domain.SetData(KEY_WINDOW, None)

    idling = EventHandler[IdlingEventArgs](_on_idling)
    view = EventHandler[ViewActivatedEventArgs](_on_view_activated)
    uiapp.Idling += idling
    uiapp.ViewActivated += view
    # keep references so the delegates are not garbage collected
    domain.SetData(KEY_IDLING, idling)
