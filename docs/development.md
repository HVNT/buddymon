# Development

## Setup

No package install is required for normal runtime use.

For tests:

```
uv run --with pytest --with pillow --no-project python3 -m pytest tests/ -q
```

Pillow is needed because some tests cover image import and sprite-pack tooling.

## Useful Commands

```
python3 buddymon.py menu
python3 buddymon.py menu tokens
python3 buddymon.py tokens
python3 buddymon.py collect
python3 buddymon.py status
python3 buddymon.py dex --list
python3 buddymon.py preview
python3 buddymon.py tiny --collect
```

## Optional Asset Tools

These write to `~/.local/state/buddymon/packs/`. Do not commit generated
packs.

```
uv run --with pillow --no-project python3 tools/fetch_official.py
uv run --with pillow --no-project python3 tools/fetch_box.py
uv run --with pillow --no-project python3 tools/fetch_gen5.py
```

## Before Pushing

Run the full test command and keep `git status --short` clean except for files
you intentionally changed.
