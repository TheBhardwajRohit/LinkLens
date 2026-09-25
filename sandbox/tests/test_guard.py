import ipaddress

import pytest

from app.guard import Blocked, Guard, ip_block_reason
from tests.conftest import fake_resolver

BLOCKED_IPS = [
    "127.0.0.1",
    "127.8.9.10",
    "10.1.2.3",
    "172.16.0.1",
    "172.31.255.255",
    "192.168.0.1",
    "169.254.169.254",  # cloud metadata
    "169.254.1.1",
    "100.64.0.1",  # carrier-grade NAT
    "0.0.0.0",
    "224.0.0.1",
    "255.255.255.255",
    "198.18.0.1",
    "192.0.2.1",
    "::",
    "::1",
    "fe80::1",
    "fc00::1",
    "fd00:ec2::254",  # AWS metadata over IPv6
    "::ffff:127.0.0.1",  # IPv4-mapped IPv6
    "::ffff:10.0.0.1",
    "64:ff9b::a00:1",  # NAT64 form of 10.0.0.1
    "2002:a00:1::",  # 6to4 form of 10.0.0.1
    "ff02::1",
]

PUBLIC_IPS = ["8.8.8.8", "1.1.1.1", "93.184.215.14", "2606:4700:4700::1111", "::ffff:8.8.8.8"]


@pytest.mark.parametrize("ip", BLOCKED_IPS)
def test_private_and_special_ips_are_blocked(ip):
    assert ip_block_reason(ipaddress.ip_address(ip)) is not None


@pytest.mark.parametrize("ip", PUBLIC_IPS)
def test_public_ips_are_allowed(ip):
    assert ip_block_reason(ipaddress.ip_address(ip)) is None


def test_metadata_gets_a_clear_reason():
    assert ip_block_reason(ipaddress.ip_address("169.254.169.254")) == "cloud metadata address"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "app.localhost",
        "127.0.0.1",
        "[::1]",
        "10.0.0.1",
        # Other ways of writing 127.0.0.1 that the system resolver understands.
        "2130706433",
        "0x7f.1",
        "017700000001",
    ],
)
async def test_local_hosts_are_blocked(host):
    with pytest.raises(Blocked):
        await Guard().check(host, 80)


@pytest.mark.anyio
@pytest.mark.parametrize("port", [0, 21, 22, 25, 445, 1023, 65536])
async def test_non_web_ports_are_blocked(port):
    with pytest.raises(Blocked, match="not a web port"):
        await Guard(resolver=fake_resolver({"public.test": ["8.8.8.8"]})).check("public.test", port)


@pytest.mark.anyio
@pytest.mark.parametrize("port", [80, 443, 8080, 8443])
async def test_web_ports_are_allowed(port):
    allowed = await Guard(resolver=fake_resolver({"public.test": ["8.8.8.8"]})).check("public.test", port)
    assert allowed.ip == "8.8.8.8"


@pytest.mark.anyio
async def test_a_name_with_one_private_address_is_blocked():
    guard = Guard(resolver=fake_resolver({"mixed.test": ["93.184.215.14", "10.0.0.1"]}))
    with pytest.raises(Blocked, match="private"):
        await guard.check("mixed.test", 443)


@pytest.mark.anyio
async def test_a_public_name_pointing_at_this_machine_is_blocked():
    guard = Guard(resolver=fake_resolver({"rebind.test": ["127.0.0.1"]}))
    with pytest.raises(Blocked, match="local"):
        await guard.check("rebind.test", 80)


@pytest.mark.anyio
async def test_unknown_names_are_blocked():
    with pytest.raises(Blocked, match="could not be found"):
        await Guard(resolver=fake_resolver({})).check("nope.test", 443)


@pytest.mark.anyio
async def test_allow_list_is_exact_ip_and_port():
    guard = Guard(
        resolver=fake_resolver({"site.test": ["127.0.0.1"]}), allow=frozenset({("127.0.0.1", 8123)})
    )
    assert (await guard.check("site.test", 8123)).ip == "127.0.0.1"
    with pytest.raises(Blocked):
        await guard.check("site.test", 8124)
