"""Config for message bus tests
"""
import pytest
import aiokafka
import kafka3
from kafka3.future import Future


@pytest.fixture
def aio_kafka_producer_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    """Fixture providing a mock kafka producer

    :param monkeypatch: Pytest monkeypatch
    :type monkeypatch: :class:`pytest`.`MonkeyPatch`
    :return: List of actions performed
    :rtype: `list`[`str`]
    """
    action_list = []

    async def mock_send_wait(*args, **kwargs):
        action_list.append("send")
        return ""

    async def mock_start(*agrs, **kwargs):
        action_list.append("start")
        return None

    async def mock_stop(*agrs, **kwargs):
        action_list.append("stop")
        return None
    monkeypatch.setattr(
        aiokafka.AIOKafkaProducer, "send_and_wait", mock_send_wait
    )
    monkeypatch.setattr(
        aiokafka.AIOKafkaProducer, "start", mock_start
    )
    monkeypatch.setattr(
        aiokafka.AIOKafkaProducer, "stop", mock_stop
    )
    return action_list


@pytest.fixture
def sync_kafka_producer_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    """Fixture providing a mock kafka producer

    :param monkeypatch: Pytest monkeypatch
    :type monkeypatch: :class:`pytest`.`MonkeyPatch`
    :return: List of actions performed
    :rtype: `list`[`str`]
    """
    action_list = []

    def mock_send(*args, **kwargs):
        action_list.append("send")
        future = Future()
        future.success("")
        return future

    def mock_start(*agrs, **kwargs):
        action_list.append("start")
        return None

    def mock_stop(*agrs, **kwargs):
        action_list.append("stop")
        return None
    monkeypatch.setattr(
        kafka3.KafkaProducer, "send", mock_send
    )
    monkeypatch.setattr(
        kafka3.KafkaProducer, "__init__", mock_start
    )
    monkeypatch.setattr(
        kafka3.KafkaProducer, "close", mock_stop
    )
    return action_list
