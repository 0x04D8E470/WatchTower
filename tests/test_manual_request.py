import pytest
import httpx
from app.utils.http_client import HttpTimeoutError

@pytest.mark.asyncio
async def test_execute_success(manual_request_service, mocker):
    mock_response = httpx.Response(status_code=200, headers={"Content-Type": "text/plain"}, content=b"Hello!")
    mocker.patch("app.services.manual_request.http_client.fetch_url", return_value=mock_response)

    result = await manual_request_service.execute("GET", "https://example.com")

    assert result["ok"] is True
    assert result["status_code"] == 200
    assert result["body"] == "Hello!"
    assert not result.get("is_binary")

@pytest.mark.asyncio
async def test_execute_timeout(manual_request_service, mocker):
    mocker.patch("app.services.manual_request.http_client.fetch_url", side_effect=HttpTimeoutError("Таймаут"))

    result = await manual_request_service.execute("GET", "https://example.com")

    assert result["ok"] is False
    assert "Таймаут" in result["error"]

@pytest.mark.asyncio
async def test_binary_response(manual_request_service, mocker):
    mock_response = httpx.Response(
        status_code=200,
        headers={"Content-Type": "image/png"},
        content=b"\x89PNG",
    )
    mocker.patch("app.services.manual_request.http_client.fetch_url", return_value=mock_response)

    result = await manual_request_service.execute("GET", "https://example.com/photo.png")

    assert result["ok"] is True
    assert result["status_code"] == 200
    # Теперь для бинарного ответа тело содержит специальное сообщение
    assert "Бинарные данные:" in result["body"]
    assert "байт" in result["body"]