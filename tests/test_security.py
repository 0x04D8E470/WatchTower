import pytest
from app.services.request_service import RequestService

@pytest.fixture
def request_service_for_validation():
    return RequestService(manual_request=None, repo=None)

@pytest.mark.asyncio
async def test_validate_url_allows_public(request_service_for_validation):
    try:
        await request_service_for_validation._validate_url("https://google.com")
    except ValueError as e:
        pytest.fail(f"Public URL should be allowed, but got: {e}")

@pytest.mark.asyncio
async def test_validate_url_blocks_localhost(request_service_for_validation):
    with pytest.raises(ValueError, match="Адрес ведёт на локальную машину"):
        await request_service_for_validation._validate_url("http://localhost:8080")

@pytest.mark.asyncio
async def test_validate_url_blocks_private_ip(request_service_for_validation, mocker):
    # Подменяем DNS-резолвинг, чтобы хост private.local резолвился в приватный IP
    mocker.patch("socket.getaddrinfo", return_value=[
        (2, 1, 6, '', ('192.168.1.1', 0))
    ])
    with pytest.raises(ValueError, match="Запрещённый IP-адрес"):
        await request_service_for_validation._validate_url("http://private.local")