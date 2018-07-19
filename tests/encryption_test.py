# -*- coding: utf-8 -*-

import os
import pytest

from olm import Account, OutboundSession, OutboundGroupSession

from nio.encryption import (KeyStore, Olm, OlmDevice, OlmSession, OneTimeKey,
                            SessionStore, Ed25519Key, DeviceStore, Key,
                            OlmTrustError)


AliceId = "@alice:example.org"
Alice_device = "ALDEVICE"

BobId = "@bob:example.org"
Bob_device = "BOBDEVICE"


class TestClass(object):
    @property
    def _test_dir(self):
        return os.path.join(os.curdir, "tests/data/encryption")

    def test_new_account_creation(self):
        olm = Olm("ephermal", "DEVICEID", self._test_dir)
        assert isinstance(olm.account, Account)
        os.remove(os.path.join(self._test_dir, "ephermal_DEVICEID.db"))

    def _load(self, user_id, device_id):
        return Olm(user_id, device_id, self._test_dir)

    def test_account_loading(self):
        olm = self._load("example", "DEVICEID")
        assert isinstance(olm.account, Account)
        assert (olm.account.identity_keys["curve25519"]
                == "RKSnNbkK6hjhbrMLPgeVrSeRAblXkqni9TrQ1EWqcRE")
        assert (olm.account.identity_keys["ed25519"]
                == "7ghkECn0yUiDEDpd7C03ErLItloNU1hNvwqpmkxl6qU")

    def test_fingerprint_store(self, monkeypatch):
        def mocksave(self):
            return

        monkeypatch.setattr(KeyStore, '_save', mocksave)
        store = KeyStore(os.path.join(
            self._test_dir,
            "ephermal_devices"
        ))
        account = Account()
        device = OlmDevice("example", "DEVICEID", account.identity_keys)
        key = Key.from_olmdevice(device)

        assert key not in store
        assert store.add(key)
        assert key in store
        assert store.remove(key)
        assert store.check(key) is False

    def test_fingerprint_store_loading(self):
        store = KeyStore(os.path.join(self._test_dir, "known_devices"))
        key = Ed25519Key(
            "example",
            "DEVICEID",
            "2MX1WOCAmE9eyywGdiMsQ4RxL2SIKVeyJXiSjVFycpA"
        )

        assert key in store

    def test_invalid_store_entry_equality(self):
        entry = Ed25519Key(
            "example",
            "DEVICEID",
            "2MX1WOCAmE9eyywGdiMsQ4RxL2SIKVeyJXiSjVFycpA"
        )

        assert entry != 1

    def test_differing_store_entries(self):
        alice = Ed25519Key(
            "alice",
            "DEVICEID",
            "2MX1WOCAmE9eyywGdiMsQ4RxL2SIKVeyJXiSjVFycpA"
        )

        bob = Ed25519Key(
            "bob",
            "DEVICEDI",
            "3MX1WOCAmE9eyywGdiMsQ4RxL2SIKVeyJXiSjVFycpA"
        )

        assert alice != bob

    def test_str_device(self):
        device = OlmDevice(
            "example",
            "DEVICEID",
            {"ed25519": "2MX1WOCAmE9eyywGdiMsQ4RxL2SIKVeyJXiSjVFycpA"}
        )
        device_str = ("example DEVICEID " "{'ed25519': "
                      "'2MX1WOCAmE9eyywGdiMsQ4RxL2SIKVeyJXiSjVFycpA'}")
        assert str(device) == device_str

    def test_invalid_device_equality(self):
        device = OlmDevice(
            "example",
            "DEVICEID",
            {"ed25519": "2MX1WOCAmE9eyywGdiMsQ4RxL2SIKVeyJXiSjVFycpA"}
        )
        assert device != 1

    def test_uknown_key_equality(self):
        alice = OlmDevice(
            "example",
            "DEVICEID",
            {"ed25519": "2MX1WOCAmE9eyywGdiMsQ4RxL2SIKVeyJXiSjVFycpA"}
        )
        bob = OlmDevice(
            "example",
            "DEVICEID",
            {"rsa": "2MX1WOCAmE9eyywGdiMsQ4RxL2SIKVeyJXiSjVFycpA"}
        )
        assert alice != bob

    def test_one_time_key_creation(self):
        key = OneTimeKey(
            "example",
            "DEVICEID",
            "ubIIABa6OJqXKBgjTBweu9byDQ6bRcv+1Ha5zZ8Sv3M",
            "curve25519"
        )
        assert isinstance(key, OneTimeKey)

    def _create_session(self):
        alice = Account()
        bob = Account()
        bob.generate_one_time_keys(1)
        one_time = list(bob.one_time_keys["curve25519"].values())[0]
        OneTimeKey(BobId, Bob_device, one_time, "curve25519")
        id_key = bob.identity_keys["curve25519"]
        s = OutboundSession(alice, id_key, one_time)
        return alice, bob, s

    def test_session_store(self):
        alice, bob, s = self._create_session()
        session = OlmSession(
            BobId,
            Bob_device,
            bob.identity_keys["curve25519"],
            s
        )
        store = SessionStore()
        store.add(session)
        assert store.check(session)
        assert session in store

    def test_session_store_sort(self):
        alice, bob, s = self._create_session()
        bob.generate_one_time_keys(1)
        one_time = list(bob.one_time_keys["curve25519"].values())[0]
        id_key = bob.identity_keys["curve25519"]
        s2 = OutboundSession(alice, id_key, one_time)

        session = OlmSession(BobId, Bob_device, id_key, s)
        session2 = OlmSession(BobId, Bob_device, id_key, s2)
        store = SessionStore()
        store.add(session)
        store.add(session2)

        if session.session.id < session2.session.id:
            assert session == store.get(id_key)
        else:
            assert session2 == store.get(id_key)

    def test_device_store(self):
        alice = OlmDevice(
            "example",
            "DEVICEID",
            {"ed25519": "2MX1WOCAmE9eyywGdiMsQ4RxL2SIKVeyJXiSjVFycpA"}
        )

        store = DeviceStore(os.path.join(
            self._test_dir,
            "ephermal_devices"
        ))

        assert store.add(alice)
        assert store.add(alice) is False
        assert alice in store
        os.remove(os.path.join(self._test_dir, "ephermal_devices"))

    def test_device_load(self, monkeypatch):
        def mocksave(self):
            return

        monkeypatch.setattr(KeyStore, '_save', mocksave)

        alice = OlmDevice(
            "example",
            "DEVICEID",
            {"ed25519": "2MX1WOCAmE9eyywGdiMsQ4RxL2SIKVeyJXiSjVFycpA"}
        )
        store = DeviceStore(os.path.join(self._test_dir, "known_devices"))
        assert (Key.from_olmdevice(alice) in store._fingerprint_store)
        assert store.add(alice)
        assert alice in store

    def test_device_invalid(self, monkeypatch):
        def mocksave(self):
            return

        monkeypatch.setattr(KeyStore, '_save', mocksave)
        eve = OlmDevice(
            "example",
            "DEVICEID",
            {"ed25519": "3MX2WOCAmE0eyywGdiMsQ4RxL2SIKVeyJXiSjVFycpB"}
        )
        store = DeviceStore(os.path.join(self._test_dir, "known_devices"))
        with pytest.raises(OlmTrustError):
            store.add(eve)

    def test_olm_outbound_session_create(self, monkeypatch):
        def mocksave(self):
            return

        monkeypatch.setattr(KeyStore, '_save', mocksave)

        bob = Account()
        bob.generate_one_time_keys(1)
        one_time = list(bob.one_time_keys["curve25519"].values())[0]

        bob_device = OlmDevice(BobId, Bob_device, bob.identity_keys)

        olm = Olm("ephermal", "DEVICEID", self._test_dir)
        olm.devices.add(bob_device)
        olm.create_session(BobId, Bob_device, one_time)
        assert olm.session_store.get(bob.identity_keys["curve25519"])
        os.remove(os.path.join(self._test_dir, "ephermal_DEVICEID.db"))

    def test_olm_session_load(self):
        olm = self._load("example", "DEVICEID")
        bob_session = olm.session_store.get(
            "W4pNkTQs6iwJLquwTSWrPDIp54RzjN3SsnDMK9+uOG4"
        )
        assert bob_session
        assert (bob_session.session.id
                == "QFRswzEBDl8rSG2drxPQ8rx5gWkr/GF3+E3dwDnOeBo")

    def test_olm_group_session_store(self):
        try:
            olm = Olm("ephermal", "DEVICEID", self._test_dir)
            bob_account = Account()
            outbound_session = OutboundGroupSession()
            olm.create_group_session(
                bob_account.identity_keys["curve25519"],
                bob_account.identity_keys["ed25519"],
                "!test_room",
                outbound_session.id,
                outbound_session.session_key)

            del olm

            olm = self._load("ephermal", "DEVICEID")

            bob_session = olm.inbound_group_store.get(
                "!test_room",
                outbound_session.id
            )

            assert bob_session
            assert (bob_session.id
                    == outbound_session.id)

        finally:
            os.remove(os.path.join(self._test_dir, "ephermal_DEVICEID.db"))

    def test_olm_inbound_session(self, monkeypatch):
        def mocksave(self):
            return

        monkeypatch.setattr(KeyStore, '_save', mocksave)

        # create two new accounts
        alice = self._load(AliceId, Alice_device)
        bob = self._load(BobId, Bob_device)

        # create olm devices for each others known devices list
        alice_device = OlmDevice(
            AliceId,
            Alice_device,
            alice.account.identity_keys
        )
        bob_device = OlmDevice(BobId, Bob_device, bob.account.identity_keys)

        # add the devices to the device list
        alice.devices.add(bob_device)
        bob.devices.add(alice_device)

        # bob creates one time keys
        bob.account.generate_one_time_keys(1)
        one_time = list(bob.account.one_time_keys["curve25519"].values())[0]
        # Mark the keys as published
        bob.account.mark_keys_as_published()

        # alice creates an outbound olm session with bob
        alice.create_session(BobId, Bob_device, one_time)

        session = alice.session_store.get(bob_device.keys["curve25519"])

        group_session = OutboundGroupSession()

        payload_dict = {
            "type": "m.room_key",
            "content": {
                "algorithm": "m.megolm.v1.aes-sha2",
                "room_id": "!test:example.org",
                "session_id": group_session.id,
                "session_key": group_session.session_key,
                "chain_index": group_session.message_index
            },
            "sender": AliceId,
            "sender_device": Alice_device,
            "keys": {
                "ed25519": alice_device.keys["ed25519"]
            },
            "recipient": BobId,
            "recipient_keys": {
                "ed25519": bob_device.keys["ed25519"]
            }
        }

        # alice encrypts the payload for bob
        message = session.encrypt(Olm._to_json(payload_dict))

        # bob decrypts the message and creates a new inbound session with alice
        try:
            # pdb.set_trace()
            bob.decrypt(AliceId, alice_device.keys["curve25519"], message)

            # we check that the session is there
            assert bob.session_store.get(alice_device.keys["curve25519"])
            # we check that the group session is there
            assert bob.inbound_group_store.get(
                "!test:example.org",
                group_session.id
            )

        finally:
            # remove the databases, the known devices store is handled by
            # monkeypatching
            os.remove(os.path.join(
                self._test_dir,
                "{}_{}.db".format(AliceId, Alice_device)
            ))
            os.remove(os.path.join(
                self._test_dir,
                "{}_{}.db".format(BobId, Bob_device)
            ))