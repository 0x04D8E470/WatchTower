import pytest
from unittest.mock import AsyncMock, patch
from app.db.models.monitor import Monitor
from app.utils.http_client import HttpNetworkError

@pytest.mark.asyncio
async def test_check_monitor_up_status_change(monitor_service, mock_monitor_repo, mocker):
    monitor = Monitor(
        id=1, user_id=123, url="https://example.com", method="GET",
        expected_status=200, check_interval=300, last_status="unknown", is_active=True
    )
    mock_response = mocker.AsyncMock()
    mock_response.status_code = 200
    mocker.patch("app.services.monitor.http_client.fetch_url", return_value=mock_response)

    result, changed = await monitor_service.check_monitor(monitor)

    assert result.is_up is True
    assert changed is True
    mock_monitor_repo.add_check_result.assert_awaited_once()
    mock_monitor_repo.update.assert_awaited_once_with(monitor)
    assert monitor.last_status == "up"

@pytest.mark.asyncio
async def test_check_monitor_down_status_change(monitor_service, mock_monitor_repo, mocker):
    monitor = Monitor(
        id=2, user_id=123, url="https://fail.com", method="GET",
        expected_status=200, last_status="up", is_active=True
    )
    mocker.patch("app.services.monitor.http_client.fetch_url", side_effect=HttpNetworkError("Сеть недоступна"))

    result, changed = await monitor_service.check_monitor(monitor)

    assert result.is_up is False
    assert result.error_message is not None
    assert changed is True
    assert monitor.last_status == "down"