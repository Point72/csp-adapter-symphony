#!/usr/bin/env python
"""Symphony CSP End-to-End Integration Test.

This script tests all Symphony functionality through the CSP adapter.
Uses CSP for message streaming (subscribe/publish), runs other operations
via async setup before the CSP graph starts.

Environment Variables Required:
    SYMPHONY_HOST: Your Symphony pod hostname
    SYMPHONY_BOT_USERNAME: Bot's service account username
    SYMPHONY_TEST_ROOM_NAME: Room where tests run
    SYMPHONY_TEST_USER_NAME: Username for mention tests

    Authentication (one of):
    SYMPHONY_BOT_PRIVATE_KEY_PATH: Path to RSA private key file
    SYMPHONY_BOT_PRIVATE_KEY_CONTENT: RSA private key content
    SYMPHONY_BOT_COMBINED_CERT_PATH: Path to combined cert file
    SYMPHONY_BOT_COMBINED_CERT_CONTENT: Combined cert content

Usage:
    python -m csp_adapter_symphony.tests.integration.symphony_csp_e2e
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional

import csp
from chatom.base import Channel, Message
from chatom.format import Format, FormattedMessage, Table
from chatom.symphony import SymphonyBackend, SymphonyConfig, SymphonyMessage
from chatom.symphony.mention import format_cashtag, format_hashtag, mention_user_by_uid
from chatom.symphony.presence import SymphonyPresenceStatus
from csp import ts

from csp_adapter_symphony.v1 import SymphonyAdapter


def get_env(name: str, required: bool = True) -> Optional[str]:
    """Get environment variable with validation."""
    value = os.environ.get(name)
    if required and not value:
        print(f"❌ Missing required environment variable: {name}")
        sys.exit(1)
    return value


def build_config() -> SymphonyConfig:
    """Build SymphonyConfig from environment variables."""
    host = get_env("SYMPHONY_HOST")
    bot_username = get_env("SYMPHONY_BOT_USERNAME")
    private_key_path = get_env("SYMPHONY_BOT_PRIVATE_KEY_PATH", required=False)
    private_key_content = get_env("SYMPHONY_BOT_PRIVATE_KEY_CONTENT", required=False)
    combined_cert_path = get_env("SYMPHONY_BOT_COMBINED_CERT_PATH", required=False) or get_env("SYMPHONY_CERTIFICATE_PATH", required=False)
    combined_cert_content = get_env("SYMPHONY_BOT_COMBINED_CERT_CONTENT", required=False)

    if not (private_key_path or private_key_content or combined_cert_path or combined_cert_content):
        print("❌ Authentication required.")
        sys.exit(1)

    config_kwargs = {"host": host, "bot_username": bot_username}

    if private_key_path:
        config_kwargs["bot_private_key_path"] = private_key_path
    elif private_key_content:
        config_kwargs["bot_private_key_content"] = private_key_content
    elif combined_cert_path:
        config_kwargs["bot_certificate_path"] = combined_cert_path
    elif combined_cert_content:
        config_kwargs["bot_certificate_content"] = combined_cert_content

    # Optional hosts
    for env_name, config_name in [
        ("SYMPHONY_AGENT_HOST", "agent_host"),
        ("SYMPHONY_SESSION_AUTH_HOST", "session_auth_host"),
        ("SYMPHONY_KEY_MANAGER_HOST", "key_manager_host"),
    ]:
        value = get_env(env_name, required=False) or get_env(env_name.replace("SYMPHONY_", ""), required=False)
        if value:
            config_kwargs[config_name] = value

    # Optional URL overrides
    for env_name, config_name in [
        ("SYMPHONY_MESSAGE_CREATE_URL", "message_create_url"),
        ("SYMPHONY_DATAFEED_CREATE_URL", "datafeed_create_url"),
        ("SYMPHONY_DATAFEED_DELETE_URL", "datafeed_delete_url"),
        ("SYMPHONY_DATAFEED_READ_URL", "datafeed_read_url"),
        ("SYMPHONY_ROOM_SEARCH_URL", "room_search_url"),
        ("SYMPHONY_ROOM_INFO_URL", "room_info_url"),
        ("SYMPHONY_IM_CREATE_URL", "im_create_url"),
        ("SYMPHONY_ROOM_MEMBERS_URL", "room_members_url"),
        ("SYMPHONY_PRESENCE_URL", "presence_url"),
        ("SYMPHONY_USER_DETAIL_URL", "user_detail_url"),
        ("SYMPHONY_USER_SEARCH_URL", "user_search_url"),
        ("SYMPHONY_USER_LOOKUP_URL", "user_lookup_url"),
    ]:
        value = get_env(env_name, required=False)
        if value:
            config_kwargs[config_name] = value

    return SymphonyConfig(**config_kwargs)


class TestState:
    """Container for test state."""

    def __init__(self):
        self.results: List[tuple] = []
        self.config: Optional[SymphonyConfig] = None
        self.channel_id: Optional[str] = None  # Generic field, not backend-specific
        self.user_id: Optional[str] = None
        self.bot_user_id: Optional[str] = None
        self.bot_display_name: Optional[str] = None
        self.received_message: Optional[Message] = None
        self.waiting_for_inbound: bool = False
        self.test_complete: bool = False

    def log(self, message: str, success: bool = True):
        icon = "✅" if success else "❌"
        print(f"{icon} {message}")
        self.results.append((message, success))

    def section(self, title: str):
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}\n")

    def print_summary(self) -> bool:
        self.section("Test Summary")
        passed = sum(1 for _, s in self.results if s)
        failed = sum(1 for _, s in self.results if not s)
        total = len(self.results)
        print(f"  Passed: {passed}/{total}")
        print(f"  Failed: {failed}/{total}")
        if failed > 0:
            print("\n  Failed tests:")
            for msg, success in self.results:
                if not success:
                    print(f"    ❌ {msg}")
        return failed == 0


# Globals
STATE = TestState()
ROOM_NAME = get_env("SYMPHONY_TEST_ROOM_NAME")
USER_NAME = get_env("SYMPHONY_TEST_USER_NAME")


async def setup_and_run_pre_csp_tests():
    """Run tests that require async operations before CSP starts."""
    STATE.config = build_config()
    backend = SymphonyBackend(config=STATE.config)

    # Test: Connection
    STATE.section("Test: Connection")
    await backend.connect()
    STATE.log("Connected to Symphony successfully")
    print(f"  Backend: {backend.name}")
    print(f"  Format: {backend.format}")

    # Resolve room
    STATE.section("Resolving Room")
    channel = await backend.fetch_channel(name=ROOM_NAME)
    if channel:
        STATE.channel_id = channel.id
        STATE.log(f"Found room '{ROOM_NAME}'")
        print(f"  Channel ID: {STATE.channel_id}")
    else:
        STATE.log(f"Room '{ROOM_NAME}' not found", success=False)
        return False

    # Resolve user
    STATE.section("Resolving User")
    user = await backend.fetch_user(handle=USER_NAME)
    if not user:
        user = await backend.fetch_user(name=USER_NAME)
    if user:
        STATE.user_id = user.id
        STATE.log(f"Found user '{user.name}'")
        print(f"  User ID: {STATE.user_id}")
    else:
        STATE.log(f"User '{USER_NAME}' not found", success=False)
        return False

    # Get bot info
    STATE.section("Getting Bot Info")
    bot_info = await backend.get_bot_info()
    if bot_info:
        STATE.bot_user_id = bot_info.id
        STATE.bot_display_name = bot_info.name
        STATE.log(f"Bot: {bot_info.name} ({bot_info.id})")
    else:
        STATE.log("Could not get bot info", success=False)
        return False

    # Fetch message history (test)
    STATE.section("Test: Fetch Message History")
    history = await backend.fetch_messages(STATE.channel_id, limit=5)
    STATE.log(f"Fetched {len(history)} messages from history")
    for m in history[:3]:
        preview = (m.content or "")[:40].replace("\n", " ")
        print(f"  - {preview}...")

    # Create DM (test)
    STATE.section("Test: Create DM")
    im_id = await backend.create_im([STATE.user_id])
    if im_id:
        STATE.log(f"Created DM: {im_id[:20]}...")
        msg = FormattedMessage().add_text("🧪 [CSP E2E] DM test message (async)")
        await backend.send_message(im_id, msg.render(Format.SYMPHONY_MESSAGEML))
        STATE.log("Sent message to DM")
    else:
        STATE.log("Failed to create DM", success=False)

    # Create room (test)
    STATE.section("Test: Create Room")
    room_name = f"CSP E2E {datetime.now().strftime('%H%M%S')}"
    room_id = await backend.create_room(name=room_name, description="CSP E2E test", public=False)
    if room_id:
        STATE.log(f"Created room: {room_name}")
        msg = FormattedMessage().add_text(f"🧪 [CSP E2E] Room test (async) - {room_name}")
        await backend.send_message(room_id, msg.render(Format.SYMPHONY_MESSAGEML))
        STATE.log("Sent message to room")
    else:
        STATE.log("Failed to create room", success=False)

    # Disconnect (CSP will create its own connection)
    await backend.disconnect()
    STATE.log("Disconnected (pre-CSP setup complete)")

    return True


@csp.graph
def symphony_csp_e2e_graph():
    """CSP graph for message streaming tests."""
    adapter = SymphonyAdapter(STATE.config)

    # Subscribe to all messages
    messages = adapter.subscribe()

    # Test messages to send
    @csp.node
    def message_sender() -> ts[SymphonyMessage]:
        """Send test messages via CSP publish."""
        with csp.alarms():
            a_step = csp.alarm(int)

        with csp.start():
            csp.schedule_alarm(a_step, timedelta(milliseconds=500), 0)

        if csp.ticked(a_step):
            step = a_step

            if step == 0:
                # Send plain message
                STATE.section("Test: Send Plain Message (via CSP)")
                timestamp = datetime.now().strftime("%H:%M:%S")
                msg = FormattedMessage().add_text(f"🧪 [CSP E2E] Plain message at {timestamp}")
                STATE.log(f"Sending plain message at {timestamp}")
                csp.schedule_alarm(a_step, timedelta(seconds=1), 1)
                return SymphonyMessage(channel=Channel(id=STATE.channel_id), content=msg.render(Format.SYMPHONY_MESSAGEML))

            elif step == 1:
                # Send MessageML
                STATE.section("Test: Send MessageML (via CSP)")
                msg = (
                    FormattedMessage()
                    .add_text("🧪 [CSP E2E] MessageML:\n")
                    .add_bold("Bold")
                    .add_text(" and ")
                    .add_italic("italic")
                    .add_text("\nCode: ")
                    .add_code("inline_code()")
                )
                STATE.log("Sending MessageML message")
                csp.schedule_alarm(a_step, timedelta(seconds=1), 2)
                return SymphonyMessage(channel=Channel(id=STATE.channel_id), content=msg.render(Format.SYMPHONY_MESSAGEML))

            elif step == 2:
                # Mentions
                STATE.section("Test: Mentions (via CSP)")
                mention = mention_user_by_uid(STATE.user_id)
                msg = FormattedMessage().add_text("🧪 [CSP E2E] Mention: ").add_raw(mention)
                STATE.log("Sending mention message")
                csp.schedule_alarm(a_step, timedelta(seconds=1), 3)
                return SymphonyMessage(channel=Channel(id=STATE.channel_id), content=msg.render(Format.SYMPHONY_MESSAGEML))

            elif step == 3:
                # Hashtags/Cashtags
                STATE.section("Test: Hashtags/Cashtags (via CSP)")
                hashtag = format_hashtag("chatom")
                cashtag = format_cashtag("AAPL")
                msg = FormattedMessage().add_text("🧪 [CSP E2E] ").add_raw(hashtag).add_text(" ").add_raw(cashtag)
                STATE.log("Sending hashtag/cashtag message")
                csp.schedule_alarm(a_step, timedelta(seconds=1), 4)
                return SymphonyMessage(channel=Channel(id=STATE.channel_id), content=msg.render(Format.SYMPHONY_MESSAGEML))

            elif step == 4:
                # Table
                STATE.section("Test: Rich Content Table (via CSP)")
                msg = FormattedMessage().add_text("🧪 [CSP E2E] Table:\n\n")
                table = Table.from_data(
                    headers=["Feature", "Status"],
                    data=[["Subscribe", "✅"], ["Publish", "✅"], ["Presence", "✅"]],
                )
                msg.content.append(table)
                STATE.log("Sending table message")
                csp.schedule_alarm(a_step, timedelta(seconds=1), 5)
                return SymphonyMessage(channel=Channel(id=STATE.channel_id), content=msg.render(Format.SYMPHONY_MESSAGEML))

            elif step == 5:
                # Inbound message prompt
                STATE.section("Test: Inbound Messages (via CSP subscribe)")
                msg = (
                    FormattedMessage()
                    .add_text("🧪 ")
                    .add_bold("[CSP E2E] Inbound Message Test")
                    .add_text(f"\n\nPlease @mention the bot: @{STATE.bot_display_name} hello")
                    .add_text("\n\nYou have ")
                    .add_bold("60 seconds")
                    .add_text("...")
                )
                STATE.log("Waiting for inbound message...")
                STATE.waiting_for_inbound = True
                print(f"\n  ⏳ Mention the bot: @{STATE.bot_display_name} hello")
                # Don't schedule next - wait for inbound

                return SymphonyMessage(channel=Channel(id=STATE.channel_id), content=msg.render(Format.SYMPHONY_MESSAGEML))

            elif step == 6:
                # Confirmation after inbound received
                STATE.section("Test: Inbound Message Received!")
                msg = STATE.received_message
                if msg:
                    STATE.log("Received inbound message via CSP subscribe")
                    print(f"  Message ID: {msg.id}")
                    print(f"  From: {msg.author_id}")
                    preview = (msg.content or "")[:100].replace("\n", " ")
                    print(f"  Content: {preview}...")

                    confirm = (
                        FormattedMessage()
                        .add_text("✅ ")
                        .add_bold("[CSP E2E] Message received via CSP!")
                        .add_text("\n\nYour message was received through adapter.subscribe()")
                    )
                    csp.schedule_alarm(a_step, timedelta(seconds=1), 7)
                    return SymphonyMessage(channel=Channel(id=STATE.channel_id), content=confirm.render(Format.SYMPHONY_MESSAGEML))
                else:
                    STATE.log("No message received", success=False)
                    csp.schedule_alarm(a_step, timedelta(seconds=1), 7)

            elif step == 7:
                # Done
                STATE.section("CSP Tests Complete")
                STATE.log("All CSP tests finished")
                STATE.test_complete = True
                csp.stop_engine()

    # Inbound message handler - outputs response message when user message received
    @csp.node
    def handle_inbound(msgs: ts[[Message]]) -> ts[SymphonyMessage]:
        """Handle inbound messages and output response."""
        with csp.state():
            s_found = False

        if csp.ticked(msgs) and STATE.waiting_for_inbound and not s_found:
            result = None
            for msg in msgs:
                # Skip bot's own messages
                if hasattr(msg, "author_id") and msg.author_id == STATE.bot_user_id:
                    continue
                # Got a user message
                STATE.received_message = msg
                STATE.waiting_for_inbound = False
                print(f"\n  📨 Received message: {msg.id}")
                s_found = True

                # Log and build response
                STATE.section("Test: Inbound Message Received!")
                STATE.log("Received inbound message via CSP subscribe")
                print(f"  Message ID: {msg.id}")
                print(f"  From: {msg.author_id}")
                preview = (msg.content or "")[:100].replace("\n", " ")
                print(f"  Content: {preview}...")

                confirm = (
                    FormattedMessage()
                    .add_text("✅ ")
                    .add_bold("[CSP E2E] Message received via CSP!")
                    .add_text("\n\nYour message was received through adapter.subscribe()")
                )
                result = SymphonyMessage(channel=Channel(id=STATE.channel_id), content=confirm.render(Format.SYMPHONY_MESSAGEML))

                # Mark complete
                STATE.section("CSP Tests Complete")
                STATE.log("All CSP tests finished")
                STATE.test_complete = True
                break

            if result is not None:
                return result

    sender_msgs = message_sender()
    inbound_msgs = handle_inbound(messages)

    # Merge both message streams
    @csp.node
    def merge_messages(m1: ts[SymphonyMessage], m2: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
        if csp.ticked(m1):
            return m1
        if csp.ticked(m2):
            return m2

    outbound = merge_messages(sender_msgs, inbound_msgs)

    # Stop after inbound test complete
    @csp.node
    def check_complete(msgs: ts[SymphonyMessage]):
        with csp.alarms():
            a_stop = csp.alarm(bool)
        if csp.ticked(msgs) and STATE.test_complete:
            csp.schedule_alarm(a_stop, timedelta(seconds=1), True)
        if csp.ticked(a_stop):
            csp.stop_engine()

    check_complete(inbound_msgs)

    # Publish outbound messages
    adapter.publish(outbound)

    # Presence test
    @csp.node
    def presence_sequence() -> ts[SymphonyPresenceStatus]:
        with csp.alarms():
            a_busy = csp.alarm(bool)
            a_available = csp.alarm(bool)

        with csp.start():
            csp.schedule_alarm(a_busy, timedelta(seconds=3), True)
            csp.schedule_alarm(a_available, timedelta(seconds=5), True)

        if csp.ticked(a_busy):
            print("  Setting presence to BUSY")
            STATE.log("Set presence to BUSY")
            return SymphonyPresenceStatus.BUSY

        if csp.ticked(a_available):
            print("  Setting presence to AVAILABLE")
            STATE.log("Set presence to AVAILABLE")
            return SymphonyPresenceStatus.AVAILABLE

    presence = presence_sequence()
    adapter.publish_presence(presence)


async def main_async():
    """Main async entry point."""
    print("\n" + "=" * 60)
    print("  Symphony CSP E2E Integration Test")
    print("=" * 60)

    # Phase 1: Async setup tests (fetch channel, user, create DM, room, etc.)
    print("\n--- Phase 1: Async Setup Tests ---\n")
    if not await setup_and_run_pre_csp_tests():
        return False

    # Phase 2: CSP streaming tests (publish, subscribe, presence)
    print("\n--- Phase 2: CSP Streaming Tests ---\n")
    try:
        csp.run(
            symphony_csp_e2e_graph,
            endtime=timedelta(seconds=90),
            realtime=True,
            queue_wait_time=timedelta(milliseconds=100),
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    return STATE.print_summary()


def main():
    """Main entry point."""
    success = asyncio.run(main_async())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
