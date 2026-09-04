"""Lock-aware native mutation handlers."""

import copy
import random
import time

from . import battle as battle_mode, safari, state
from .app_payloads import _build_encounter_result_payload
from .app_views import (
    SETTING_LABELS,
    _build_encounter_view,
    _setting_display_value,
    app_view,
)


def _build_action_response(action, ok=True, message="", screen=None, **extra):
    payload = {
        "schema_version": 1,
        "kind": "app_action",
        "action": action,
        "ok": bool(ok),
        "message": message,
        "generated_at": time.time(),
        **extra,
    }
    if screen:
        try:
            payload["view"] = app_view(screen)
        except Exception as exc:
            payload["view_error"] = str(exc)
    return payload


def _build_action_error_response(action, message, screen=None):
    return _build_action_response(action, ok=False, message=message, screen=screen)


def _handle_encounter_action(args):
    requested = args[0] if args else ""
    result_context = None
    encounter_snapshot = None
    with state.lock():
        s = state.load()
        if s.get("pending_battle"):
            mode = "battle"
            pending = s["pending_battle"]
            if requested == "fight":
                requested = "attack"
            outcome, message = battle_mode.take_turn(s, requested, random.Random())
        elif s.get("pending_encounter"):
            mode = "safari"
            pending = s["pending_encounter"]
            outcome, message = safari.take_turn(s, requested, random.Random())
        else:
            return _build_action_error_response(
                "encounter",
                "No wild Pokemon is waiting.",
            )
        if outcome is None:
            encounter_snapshot = copy.deepcopy(s)
        elif outcome.get("done"):
            result_context = (
                dict(state.active_pokemon(s) or {}),
                dict(pending),
                mode,
                dict(outcome),
                message,
            )
            state.save(s)
        else:
            state.save(s)
            encounter_snapshot = copy.deepcopy(s)
    if outcome is None:
        return _build_action_response(
            "encounter",
            ok=False,
            message=message,
            view=_build_encounter_view(encounter_snapshot),
        )
    if result_context:
        buddy, wild, mode, outcome, message = result_context
        return _build_action_response(
            "encounter",
            ok=True,
            message=message,
            screen=None,
            outcome=outcome,
            encounter_result=_build_encounter_result_payload(buddy, wild, mode, outcome, message),
        )
    return _build_action_response(
        "encounter",
        ok=True,
        message=message,
        view=_build_encounter_view(encounter_snapshot),
        outcome=outcome,
    )


def _next_value(values, current):
    values = tuple(values)
    if current not in values:
        return values[0]
    return values[(values.index(current) + 1) % len(values)]


def _handle_preference_action(args):
    key = args[0] if args else ""
    requested = args[1] if len(args) > 1 else None
    allowed = {"mode": state.VALID_MODES, **state.PREFERENCE_VALUES}
    if key not in allowed:
        return _build_action_error_response("preference", "Unknown preference.", screen="settings")
    with state.lock():
        s = state.load()
        prefs = state.preferences(s)
        current = s.get("mode", state.DEFAULT_MODE) if key == "mode" else prefs.get(key)
        target = requested if requested is not None else _next_value(allowed[key], current)
        if target not in allowed[key]:
            return _build_action_error_response("preference", "Invalid preference value.", screen="settings")
        if key == "mode":
            s["mode"] = target
        else:
            prefs[key] = target
        state.save(s)
    return _build_action_response(
        "preference",
        ok=True,
        message=f"{SETTING_LABELS[key]} set to {_setting_display_value(key, target)}.",
        screen="settings",
        key=key,
        value=target,
    )


APP_ACTION_HANDLERS = {
    "encounter": _handle_encounter_action,
    "preference": _handle_preference_action,
}


def app_action(action, args=None):
    action = (action or "").strip().lower()
    handler = APP_ACTION_HANDLERS.get(action)
    if handler is None:
        return _build_action_error_response(action or "unknown", "Unknown app action.")
    try:
        return handler(list(args or []))
    except Exception as exc:
        return _build_action_error_response(action, str(exc))
