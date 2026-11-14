"""Tests for Telegram QR pairing rules (pc/telegram/people.py, #71).  Owner: tests.

people.py needs no Telegram libraries, so it runs in the normal tests. Files go to a temp folder.
"""
import json
import time

import pytest

people = pytest.importorskip("pc.telegram.people", reason="Telegram pairing not in main yet (#71)")


@pytest.mark.parametrize("text", ["connect 731676", "731676", "731 676", "Connect 731-676"])
def test_the_right_code_pairs(text):
    assert people.is_pairing_code(text, "731676")


@pytest.mark.parametrize("text", ["connect 731677", "731676 731677", "123456 731676",
                                  "000000 111111 731676", "", "connect", "73167"])
def test_wrong_or_many_codes_never_pair(text):
    """A message full of numbers must not let someone try many codes at once."""
    assert not people.is_pairing_code(text, "731676")


def test_no_code_set_never_pairs():
    assert not people.is_pairing_code("connect ", "")
    assert not people.is_pairing_code("", "")


def test_five_wrong_codes_block_that_account():
    g = people.Guard()
    for _ in range(5):
        assert not g.blocked(42)
        g.miss(42)
    assert g.blocked(42)
    assert not g.blocked(7)  # someone else can still try


def test_twenty_wrong_codes_in_all_stop_pairing_for_everyone():
    g = people.Guard()
    for uid in range(20):  # 20 different accounts, one guess each
        g.miss(uid)
    assert g.blocked(999)


def test_add_remove_and_files_stay_where_told(tmp_path):
    pfile, lfile = tmp_path / "people.json", tmp_path / "live.json"
    people.add(111, "Alice", "alice", path=pfile)
    people.add(222, "Bob", path=pfile)
    assert set(people.paired(pfile)) == {111, 222}
    people.write_live("Home PC", "homepc", [{"id": 111}, {"id": 222}], path=lfile)
    assert people.remove(111, path=pfile, live_path=lfile)
    assert set(people.paired(pfile)) == {222}
    assert [p["id"] for p in json.loads(lfile.read_text())["people"]] == [222]  # the PC window updates at once
    assert not people.remove(999, path=pfile, live_path=lfile)


def test_broken_people_file_never_grants_access(tmp_path):
    pfile = tmp_path / "people.json"
    pfile.write_text('{"people": [{"id": "abc"}, "x", {"name": "no id"}, {"id": 5}]}')
    assert set(people.paired(pfile)) == {5}
    pfile.write_text("not json")
    assert people.paired(pfile) == {}


def test_stale_live_file_means_telegram_is_off(tmp_path):
    lfile = tmp_path / "live.json"
    people.write_live("Home PC", "homepc", [], path=lfile)
    assert people.live(lfile) is not None
    data = json.loads(lfile.read_text())
    data["seen"] = time.time() - 3600
    lfile.write_text(json.dumps(data))
    assert people.live(lfile) is None
