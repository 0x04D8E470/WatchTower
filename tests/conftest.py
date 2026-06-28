import pytest
from unittest.mock import AsyncMock
from app.services.manual_request import ManualRequestService
from app.services.monitor import MonitorService
from app.db.repositories.monitor_repo import MonitorRepo

@pytest.fixture
def mock_http_client():
    """Мок нашего HTTP-клиента (используется для ручного сервиса)."""
    client = AsyncMock()
    client.fetch_url = AsyncMock()
    return client

@pytest.fixture
def manual_request_service():
    """Ручной HTTP-сервис без внедрения клиента (использует глобальный http_client, который мы мокаем в тестах)."""
    return ManualRequestService()

@pytest.fixture
def mock_monitor_repo():
    """Мок репозитория мониторов."""
    repo = AsyncMock(spec=MonitorRepo)
    return repo

@pytest.fixture
def monitor_service(mock_monitor_repo):
    """MonitorService с замоканным репозиторием."""
    return MonitorService(repo=mock_monitor_repo)