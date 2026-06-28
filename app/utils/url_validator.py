import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

# Запрещённые подсети
BLOCKED_SUBNETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),   # Multicast
    ipaddress.ip_network("240.0.0.0/4"),   # Reserved
    ipaddress.ip_network("::1/128"),       # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),     # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),      # IPv6 unique local
]


def validate_url_sync(url: str) -> None:
    """
    Синхронная проверка URL на схему и чёрный список IP.
    Выбрасывает ValueError при нарушении.
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError("Некорректная схема URL")

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Не удалось извлечь хост из URL")

    # Прямые запреты (localhost, 0.0.0.0)
    if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]"):
        raise ValueError("Адрес ведёт на локальную машину")

    # Резолвим DNS (блокирующий, но вызывается из async через run_in_executor)
    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise ValueError(f"Не удалось разрешить имя хоста: {e}")

    for _, _, _, _, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        try:
            ip_addr = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for subnet in BLOCKED_SUBNETS:
            if ip_addr in subnet:
                raise ValueError(f"Запрещённый IP-адрес {ip_str} (принадлежит {subnet})")


async def validate_url(url: str) -> None:
    """Асинхронная обёртка, не блокирует event loop."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, validate_url_sync, url)