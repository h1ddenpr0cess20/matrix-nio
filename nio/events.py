# -*- coding: utf-8 -*-

# Copyright © 2018 Damir Jelić <poljar@termina.org.uk>
#
# Permission to use, copy, modify, and/or distribute this software for
# any purpose with or without fee is hereby granted, provided that the
# above copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER
# RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF
# CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
# CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

from builtins import super
from logbook import Logger
from jsonschema.exceptions import SchemaError, ValidationError
from typing import *

from .api import Api
from .log import logger_group
from .schemas import validate_json, Schemas
from .encryption import Olm

logger = Logger('nio.events')
logger_group.add_logger(logger)


def validate_or_badevent(parsed_dict, schema):
    # type: (Dict[Any, Any], Dict[Any, Any]) -> Optional[BadEvent]
    try:
        validate_json(parsed_dict, schema)
    except (ValidationError, SchemaError) as e:
        logger.error("Error validating event: {}".format(str(e)))
        return BadEvent.from_dict(parsed_dict)

    return None


class Event(object):
    def __init__(self, event_id, sender, server_ts):
        # type: (str, str, int) -> None
        self.event_id = event_id
        self.sender = sender
        self.server_timestamp = server_ts

    @classmethod
    def from_dict(cls, parsed_dict):
        # type: (Dict[Any, Any]) -> Event
        return cls(
            parsed_dict["event_id"],
            parsed_dict["sender"],
            parsed_dict["origin_server_ts"],
        )

    def __str__(self):
        return "Got event of type {} from {}.".format(
            type(self).__name__,
            self.sender
        )

    @classmethod
    def parse_event(cls, event_dict, olm=None):
        # type: (Dict[Any, Any], Optional[Olm]) -> Optional[Event]
        if "unsigned" in event_dict:
            if "redacted_because" in event_dict["unsigned"]:
                return RedactedEvent.from_dict(event_dict)

        if event_dict["type"] == "m.room.message":
            # The transaction id will only be present for events that
            # are send out from this client, since we print out our own
            # messages as soon as we get a receive confirmation from
            # the server we don't care about our own messages in a
            # sync event. More info under:
            # https://github.com/matrix-org/matrix-doc/blob/master/api/client-server/definitions/event.yaml#L53
            if "transaction_id" in event_dict["unsigned"]:
                return None

            return RoomMessage.from_dict(event_dict, olm)

        elif event_dict["type"] == "m.room.member":
            return RoomMemberEvent.from_dict(event_dict)
        elif event_dict["type"] == "m.room.canonical_alias":
            return RoomAliasEvent.from_dict(event_dict)
        elif event_dict["type"] == "m.room.name":
            return RoomNameEvent.from_dict(event_dict)
        elif event_dict["type"] == "m.room.topic":
            return RoomTopicEvent.from_dict(event_dict)
        elif event_dict["type"] == "m.room.power_levels":
            return PowerLevelsEvent.from_dict(event_dict)
        elif event_dict["type"] == "m.room.encryption":
            return RoomEncryptionEvent.from_dict(event_dict)

        return None


class BadEvent(Event):
    def __init__(self, event_id, sender, server_ts, event_type, source):
        # type: (str, str, int, str, str) -> None
        self.source = source
        self.type = event_type
        super().__init__(event_id, sender, server_ts)

    def __str__(self):
        return "Bad event of type {}, from {}.".format(
            self.sender,
            self.type
        )

    @classmethod
    def from_dict(cls, parsed_dict):
        # type: (Dict[Any, Any]) -> BadEvent
        return cls(
            parsed_dict["event_id"],
            parsed_dict["sender"],
            parsed_dict["origin_server_ts"],
            parsed_dict["type"],
            Api.to_json(parsed_dict)
        )


class RedactedEvent(Event):
    def __init__(
        self,
        event_id,    # type: str
        sender,      # type: str
        server_ts,   # type: int
        event_type,  # type: str
        redacter,    # type: str
        reason=None  # type: Optional[str]
    ):
        # type: (...) -> None
        self.event_type = event_type
        self.redacter = redacter
        self.reason = reason
        super().__init__(event_id, sender, server_ts)

    def __str__(self):
        reason = ", reason: {}".format(self.reason) if self.reason else ""
        return "Redacted event of type {}, by {}{}.".format(
            self.event_type,
            self.redacter,
            reason
        )

    @classmethod
    def from_dict(cls, parsed_dict):
        # type: (Dict[Any, Any]) -> Union[RedactedEvent, BadEvent]
        bad = validate_or_badevent(parsed_dict, Schemas.redacted_event)

        if bad:
            return bad

        redacter = parsed_dict["unsigned"]["redacted_because"]["sender"]
        content_dict = parsed_dict["unsigned"]["redacted_because"]["content"]
        reason = content_dict["reason"] if "reason" in content_dict else None

        return cls(
            parsed_dict["event_id"],
            parsed_dict["sender"],
            parsed_dict["origin_server_ts"],
            parsed_dict["type"],
            redacter,
            reason
        )


class RoomEncryptionEvent(Event):
    pass


class RoomAliasEvent(Event):
    def __init__(self, event_id, sender, server_ts, canonical_alias):
        self.canonical_alias = canonical_alias
        super().__init__(event_id, sender, server_ts)

    @classmethod
    def from_dict(cls, parsed_dict):
        # type: (Dict[Any, Any]) -> Union[RoomAliasEvent, BadEvent]
        bad = validate_or_badevent(parsed_dict, Schemas.room_canonical_alias)

        if bad:
            return bad

        event_id = parsed_dict["event_id"]
        sender = parsed_dict["sender"]
        timestamp = parsed_dict["origin_server_ts"]

        canonical_alias = parsed_dict["content"]["alias"]

        return cls(event_id, sender, timestamp, canonical_alias)


class RoomNameEvent(Event):
    def __init__(self, event_id, sender, server_ts, name):
        self.name = name
        super().__init__(event_id, sender, server_ts)

    @classmethod
    def from_dict(cls, parsed_dict):
        # type: (Dict[Any, Any]) -> Union[RoomNameEvent, BadEvent]
        bad = validate_or_badevent(parsed_dict, Schemas.room_name)

        if bad:
            return bad

        event_id = parsed_dict["event_id"]
        sender = parsed_dict["sender"]
        timestamp = parsed_dict["origin_server_ts"]

        canonical_alias = parsed_dict["content"]["name"]

        return cls(event_id, sender, timestamp, canonical_alias)


class RoomTopicEvent(Event):
    def __init__(self, event_id, sender, server_ts, topic):
        self.topic = topic
        super().__init__(event_id, sender, server_ts)

    @classmethod
    def from_dict(cls, parsed_dict):
        # type: (Dict[Any, Any]) -> Union[RoomTopicEvent, BadEvent]
        bad = validate_or_badevent(parsed_dict, Schemas.room_topic)

        if bad:
            return bad

        event_id = parsed_dict["event_id"]
        sender = parsed_dict["sender"]
        timestamp = parsed_dict["origin_server_ts"]

        canonical_alias = parsed_dict["content"]["topic"]

        return cls(event_id, sender, timestamp, canonical_alias)


class RoomMessage(Event):
    @staticmethod
    def from_dict(parsed_dict, olm=None):
        # type: (Dict[Any, Any], Any) -> Union[Event, BadEvent]
        bad = validate_or_badevent(parsed_dict, Schemas.room_message)

        if bad:
            return bad

        content_dict = parsed_dict["content"]

        if content_dict["msgtype"] == "m.text":
            return RoomMessageText.from_dict(parsed_dict)

        # TODO return unknown msgtype event
        return None


class RoomMessageText(Event):
    def __init__(
        self,
        event_id,        # type: str
        sender,          # type: str
        server_ts,       # type: int
        body,            # type: str
        formatted_body,  # type: Optional[str]
        body_format      # type: Optional[str]
    ):
        # type: (...) -> None
        super().__init__(event_id, sender, server_ts)
        self.body = body
        self.formatted_body = formatted_body
        self.format = body_format

    def __str__(self):
        # type: () -> str
        return "{}: {}".format(self.sender, self.body)

    @staticmethod
    def _validate(parsed_dict):
        # type: (Dict[Any, Any]) -> Optional[BadEvent]
        return validate_or_badevent(parsed_dict, Schemas.room_message_text)

    @classmethod
    def from_dict(cls, parsed_dict):
        # type: (Dict[Any, Any]) -> Union[RoomMessageText, BadEvent]
        bad = cls._validate(parsed_dict)

        if bad:
            return bad

        body = parsed_dict["content"]["body"]
        formatted_body = (parsed_dict["content"]["formatted_body"] if
                          "formatted_body" in parsed_dict["content"] else None)
        body_format = (parsed_dict["content"]["format"] if
                       "format" in parsed_dict["content"] else None)

        return cls(
            parsed_dict["event_id"],
            parsed_dict["sender"],
            parsed_dict["origin_server_ts"],
            body,
            formatted_body,
            body_format
        )


class RoomMessageEmote(RoomMessageText):
    @staticmethod
    def _validate(parsed_dict):
        # type: (Dict[Any, Any]) -> Optional[BadEvent]
        return validate_or_badevent(parsed_dict, Schemas.room_message_emote)


class DefaultLevels(object):
    def __init__(self):
        self.ban = 50
        self.invite = 50
        self.kick = 50
        self.redact = 50
        self.state_default = 0
        self.events_default = 0
        self.users_default = 0

    @classmethod
    def from_dict(cls, parsed_dict):
        obj = cls()
        content = parsed_dict["content"]
        obj.ban = content["ban"]
        obj.invite = content["invite"]
        obj.kick = content["kick"]
        obj.redact = content["redact"]
        obj.state_default = content["state_default"]
        obj.events_default = content["events_default"]
        obj.users_default = content["users_default"]
        return obj


class PowerLevels(object):
    def __init__(self, defaults=None, users=None, events=None):
        self.users = users or dict()
        self.events = events or dict()
        self.defaults = defaults or DefaultLevels()

    def get_user_level(self, user_id):
        # type: (str) -> int
        if user_id in self.users:
            return self.users[user_id]

        return self.defaults.users_default

    def update(self, new_levels):
        if not isinstance(new_levels, PowerLevels):
            return

        self.defaults = new_levels.defaults
        self.events.update(new_levels.events)
        self.users.update(new_levels.users)


class PowerLevelsEvent(Event):
    def __init__(
        self,
        event_id,
        sender,
        server_ts,
        power_levels
    ):
        super().__init__(event_id, sender, server_ts)
        self.power_levels = power_levels

    @classmethod
    def from_dict(cls, parsed_dict):
        bad = validate_or_badevent(parsed_dict, Schemas.room_power_levels)

        if bad:
            return bad

        default_levels = DefaultLevels.from_dict(parsed_dict)

        users = parsed_dict["content"].pop("users")
        events = parsed_dict["content"].pop("events")

        levels = PowerLevels(default_levels, users, events)

        return cls(
            parsed_dict["event_id"],
            parsed_dict["sender"],
            parsed_dict["origin_server_ts"],
            levels
        )


class RoomMemberEvent(Event):
    def __init__(
        self,
        event_id,           # type: str
        sender,             # type: str
        server_ts,          # type: int
        state_key,          # type: str
        content,            # type: Dict[str, str]
        prev_content=None   # type: Optional[Dict[str, str]]
    ):
        # type: (...) -> None
        super().__init__(event_id, sender, server_ts)
        self.state_key = state_key
        self.content = content
        self.prev_content = prev_content

    @classmethod
    def from_dict(cls, parsed_dict):
        # type: (Dict[Any, Any]) -> Union[RoomMemberEvent, BadEvent]
        bad = validate_or_badevent(parsed_dict, Schemas.room_membership)

        if bad:
            return bad

        content = parsed_dict.pop("content")
        prev_content = (parsed_dict.pop("prev_content") if "prev_content" in
                        parsed_dict else None)

        return cls(
            parsed_dict["event_id"],
            parsed_dict["sender"],
            parsed_dict["origin_server_ts"],
            parsed_dict["state_key"],
            content,
            prev_content
        )
