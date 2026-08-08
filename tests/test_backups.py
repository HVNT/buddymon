import time

import buddymon

from lib import backups, paths


def local_backup_timestamp():
    return time.mktime((2026, 7, 25, 10, 0, 0, 0, 0, -1))


def test_backup_copies_the_active_state_directory(tmp_path, monkeypatch):
    source = tmp_path / "active" / "buddymon"
    monkeypatch.setattr(paths, "STATE_DIR", source)
    monkeypatch.setattr(paths, "STATE_FILE", source / "state.json")
    source.mkdir(parents=True)
    paths.STATE_FILE.write_text('{"buddy":"charizard"}', encoding="utf-8")
    (source / "journal.jsonl").write_text('{"event":"caught"}\n', encoding="utf-8")
    pack = source / "packs" / "gen5"
    pack.mkdir(parents=True)
    (pack / "pixel.txt").write_text("local art", encoding="utf-8")

    backup = backups.create_backup(
        destination_root=tmp_path / "backups",
        now=local_backup_timestamp(),
    )

    assert backup.name == "2026-07-25_10-00-00"
    assert (backup / "state.json").read_text(encoding="utf-8") == '{"buddy":"charizard"}'
    assert (backup / "journal.jsonl").read_text(encoding="utf-8") == '{"event":"caught"}\n'
    assert (backup / "packs" / "gen5" / "pixel.txt").read_text(encoding="utf-8") == "local art"
    assert paths.STATE_FILE.read_text(encoding="utf-8") == '{"buddy":"charizard"}'


def test_backup_uses_a_new_folder_when_timestamp_collides(tmp_path, monkeypatch):
    source = tmp_path / "active" / "buddymon"
    monkeypatch.setattr(paths, "STATE_DIR", source)
    monkeypatch.setattr(paths, "STATE_FILE", source / "state.json")
    source.mkdir(parents=True)
    paths.STATE_FILE.write_text("{}", encoding="utf-8")

    root = tmp_path / "backups"
    now = local_backup_timestamp()
    first = backups.create_backup(destination_root=root, now=now)
    second = backups.create_backup(destination_root=root, now=now)

    assert first.name == "2026-07-25_10-00-00"
    assert second.name == "2026-07-25_10-00-00-1"


def test_backup_cli_uses_the_shared_backup_service(monkeypatch, tmp_path):
    destination = tmp_path / "Documents" / "BuddyMon Backups" / "snapshot"
    monkeypatch.setattr(backups, "create_backup", lambda: destination)

    assert buddymon.backup([]) == str(destination)
