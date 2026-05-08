#!/usr/bin/env python3
"""Tests for ProtonEventLoop — S5-01"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.fixture
def mock_api():
    api = MagicMock()
    api._request.return_value = {"EventID": "evt-001"}
    return api


@pytest.fixture
def event_loop_instance(mock_api):
    from src.event_loop import ProtonEventLoop
    return ProtonEventLoop(mock_api, poll_timeout=1)


class TestSubscription:
    def test_subscribe_adds_queue(self, event_loop_instance):
        q = asyncio.Queue()
        event_loop_instance.subscribe("0", q)
        assert event_loop_instance.subscriber_count() == 1

    def test_unsubscribe_removes_queue(self, event_loop_instance):
        q = asyncio.Queue()
        event_loop_instance.subscribe("0", q)
        event_loop_instance.unsubscribe("0", q)
        assert event_loop_instance.subscriber_count() == 0

    def test_multiple_subscribers_same_label(self, event_loop_instance):
        q1, q2 = asyncio.Queue(), asyncio.Queue()
        event_loop_instance.subscribe("0", q1)
        event_loop_instance.subscribe("0", q2)
        assert event_loop_instance.subscriber_count() == 2

    def test_unsubscribe_nonexistent_is_safe(self, event_loop_instance):
        q = asyncio.Queue()
        event_loop_instance.unsubscribe("nonexistent", q)  # no exception


class TestDispatch:
    @pytest.mark.asyncio
    async def test_message_create_publishes_exists(self, event_loop_instance):
        q = asyncio.Queue()
        event_loop_instance.subscribe("0", q)

        response = {
            "EventID": "evt-002",
            "Messages": [
                {
                    "Action": 1,  # CREATE
                    "ID": "msg-1",
                    "Message": {"LabelIDs": ["0"]},
                }
            ],
            "Labels": [],
        }
        await event_loop_instance._dispatch(response)
        assert not q.empty()
        event = q.get_nowait()
        assert event.event_type == "exists"
        assert event.label_id == "0"

    @pytest.mark.asyncio
    async def test_message_delete_publishes_expunge(self, event_loop_instance):
        q = asyncio.Queue()
        event_loop_instance.subscribe("5", q)

        response = {
            "EventID": "evt-003",
            "Messages": [
                {
                    "Action": 0,  # DELETE
                    "ID": "msg-x",
                    "Message": {"LabelIDs": ["5"]},
                }
            ],
            "Labels": [],
        }
        await event_loop_instance._dispatch(response)
        event = q.get_nowait()
        assert event.event_type == "expunge"

    @pytest.mark.asyncio
    async def test_label_change_publishes_cache_invalid(self, event_loop_instance):
        q = asyncio.Queue()
        event_loop_instance.subscribe("0", q)

        response = {
            "EventID": "evt-004",
            "Messages": [],
            "Labels": [{"ID": "0", "Action": 2}],
        }
        await event_loop_instance._dispatch(response)
        event = q.get_nowait()
        assert event.event_type == "cache_invalid"

    @pytest.mark.asyncio
    async def test_no_subscribers_no_error(self, event_loop_instance):
        response = {
            "EventID": "evt-005",
            "Messages": [{"Action": 1, "ID": "m", "Message": {"LabelIDs": ["0"]}}],
            "Labels": [],
        }
        await event_loop_instance._dispatch(response)  # no exception

    @pytest.mark.asyncio
    async def test_queue_full_drops_event_no_exception(self, event_loop_instance):
        q = asyncio.Queue(maxsize=1)
        q.put_nowait("sentinel")  # fill the queue
        event_loop_instance.subscribe("0", q)

        response = {
            "EventID": "evt-006",
            "Messages": [{"Action": 1, "ID": "m", "Message": {"LabelIDs": ["0"]}}],
            "Labels": [],
        }
        await event_loop_instance._dispatch(response)  # no exception, event dropped


class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_fetches_initial_event_id(self, mock_api):
        from src.event_loop import ProtonEventLoop
        mock_api._request.return_value = {"EventID": "initial-id"}
        loop = ProtonEventLoop(mock_api, poll_timeout=0.05)

        await loop.start()
        assert loop._last_event_id == "initial-id"
        await loop.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, mock_api):
        from src.event_loop import ProtonEventLoop
        mock_api._request.return_value = {"EventID": "x"}
        loop = ProtonEventLoop(mock_api, poll_timeout=0.05)
        await loop.start()
        assert loop._task is not None
        await loop.stop()
        assert loop._task.done()

    @pytest.mark.asyncio
    async def test_poll_loop_updates_event_id(self, mock_api):
        from src.event_loop import ProtonEventLoop

        calls = [0]
        def side_effect(method, endpoint):
            calls[0] += 1
            if "latest" in endpoint:
                return {"EventID": "start"}
            return {"EventID": f"evt-{calls[0]}", "Messages": [], "Labels": []}

        mock_api._request.side_effect = side_effect
        loop = ProtonEventLoop(mock_api, poll_timeout=0.05)
        await loop.start()
        await asyncio.sleep(0.2)
        await loop.stop()
        assert loop._last_event_id != "start"
