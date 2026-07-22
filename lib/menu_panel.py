"""Declarative product policy for BuddyMon's native compact panel."""

LAYOUT = "compact"

ITEMS = (
    {
        "id": "encounter",
        "label": "Handle Encounter",
        "shortcut": "e",
        "emphasis": "primary",
        "visible_when": "pending",
    },
    {
        "id": "trainer",
        "label": "Trainer",
        "shortcut": "t",
        "presentation": "utility",
    },
    {
        "id": "terminal_party",
        "label": "Party",
        "shortcut": "p",
        "terminal_screen": "party",
        "presentation": "utility",
    },
    {
        "id": "terminal_box",
        "label": "Box",
        "shortcut": "b",
        "terminal_screen": "box",
        "presentation": "utility",
    },
    {
        "id": "terminal_dex",
        "label": "Pokedex",
        "shortcut": "d",
        "terminal_screen": "dex",
        "presentation": "utility",
    },
    {
        "id": "terminal_activity",
        "label": "Activity",
        "shortcut": "a",
        "terminal_screen": "journal",
        "presentation": "utility",
    },
    {
        "id": "settings",
        "label": "Settings",
        "shortcut": "s",
        "presentation": "utility",
    },
)

TOKEN_ACTION = {
    "id": "tokens",
    "label": "Open token detail",
    "shortcut": "u",
}

FOOTER_ITEMS = (
    {
        "id": "refresh",
        "label": "Refresh",
        "shortcut": "r",
        "modifiers": ["command"],
    },
    {
        "id": "quit",
        "label": "Quit",
        "shortcut": "q",
        "modifiers": ["command"],
    },
)


def build_payload(pending):
    """Return the stable panel contract consumed by the native shell."""
    context = {
        "pending": bool(pending),
        "pending_name": pending.get("name", "Pokémon") if pending else None,
    }
    items = []
    for definition in ITEMS:
        visible_when = definition.get("visible_when")
        if visible_when and not context[visible_when]:
            continue
        item = {
            key: value
            for key, value in definition.items()
            if key != "visible_when"
        }
        if definition["id"] == "encounter":
            item["label"] = f"Wild {context['pending_name']} is waiting"
            image = pending.get("sprite_base64")
            if image:
                item["image_base64"] = image
        items.append(item)

    return {
        "layout": LAYOUT,
        "items": items,
        "token_action": dict(TOKEN_ACTION),
        "footer_items": [dict(item) for item in FOOTER_ITEMS],
    }
