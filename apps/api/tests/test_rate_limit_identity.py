"""How rate limiting decides *who* is being limited.

This is the part of rate limiting that is easy to get wrong and expensive to get
wrong: if the identity can be forged, the limit does nothing on exactly the
endpoints that need it most â€” login, registration, password reset â€” because those
have no authenticated user id to bucket by yet.

X-Forwarded-For is appended to by each proxy, so its left-most entry is supplied
by the caller. These tests pin that the caller cannot influence the bucket.
"""

import pytest
from starlette.requests import Request

from app.config import settings
from app.utils.rate_limit import _identity, resolve_client_ip

SOCKET_IP = "203.0.113.10"  # the peer the app actually sees
REAL_CLIENT = "198.51.100.7"  # the browser, per a trusted proxy
PROXY_ONE = "192.0.2.1"
FORGED = "9.9.9.9"


def make_request(
    forwarded: str | None = None,
    socket_ip: str | None = SOCKET_IP,
    user_id: str | None = None,
) -> Request:
    headers = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode()))
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": (socket_ip, 51234) if socket_ip else None,
        "server": ("testserver", 80),
    }
    request = Request(scope)
    if user_id is not None:
        request.state.user_id = user_id
    return request


@pytest.fixture
def proxy_depth(monkeypatch):
    """Set the trusted-proxy depth for a test."""

    def _set(depth: int):
        monkeypatch.setattr(settings, "trusted_proxy_count", depth, raising=False)

    return _set


class TestNoProxyConfigured:
    """Default posture: the header is not trusted at all."""

    def test_socket_peer_is_used(self, proxy_depth):
        proxy_depth(0)
        assert resolve_client_ip(make_request()) == SOCKET_IP

    def test_forwarded_header_is_ignored_entirely(self, proxy_depth):
        proxy_depth(0)
        request = make_request(forwarded=f"{FORGED}, {PROXY_ONE}")
        assert resolve_client_ip(request) == SOCKET_IP

    def test_missing_client_degrades_to_a_constant(self, proxy_depth):
        proxy_depth(0)
        assert resolve_client_ip(make_request(socket_ip=None)) == "unknown"


class TestBehindOneProxy:
    def test_honest_chain_yields_the_client(self, proxy_depth):
        proxy_depth(1)
        assert resolve_client_ip(make_request(forwarded=REAL_CLIENT)) == REAL_CLIENT

    def test_forged_entry_does_not_win(self, proxy_depth):
        """The proxy appends the true peer, so the forgery sits to its left."""
        proxy_depth(1)
        request = make_request(forwarded=f"{FORGED}, {REAL_CLIENT}")
        assert resolve_client_ip(request) == REAL_CLIENT

    def test_many_forged_entries_do_not_win(self, proxy_depth):
        proxy_depth(1)
        chain = ", ".join([FORGED] * 20 + [REAL_CLIENT])
        assert resolve_client_ip(make_request(forwarded=chain)) == REAL_CLIENT


class TestBehindTwoProxies:
    """Primo in production: Vercel's edge plus the container host's balancer."""

    def test_honest_chain_yields_the_client(self, proxy_depth):
        proxy_depth(2)
        request = make_request(forwarded=f"{REAL_CLIENT}, {PROXY_ONE}")
        assert resolve_client_ip(request) == REAL_CLIENT

    def test_forged_entry_does_not_win(self, proxy_depth):
        proxy_depth(2)
        request = make_request(forwarded=f"{FORGED}, {REAL_CLIENT}, {PROXY_ONE}")
        assert resolve_client_ip(request) == REAL_CLIENT


class TestUntrustworthyInput:
    def test_chain_shorter_than_configured_depth_falls_back(self, proxy_depth):
        """A request that skipped the proxies must not be believed."""
        proxy_depth(2)
        assert resolve_client_ip(make_request(forwarded=FORGED)) == SOCKET_IP

    @pytest.mark.parametrize(
        "value",
        [
            "not-an-ip",
            "'; DROP TABLE users; --",
            "a" * 5000,
            "127.0.0.1:8080",
            "",
        ],
    )
    def test_non_ip_values_fall_back(self, proxy_depth, value):
        """Also keeps junk out of the Redis key the bucket is stored under."""
        proxy_depth(1)
        assert resolve_client_ip(make_request(forwarded=value)) == SOCKET_IP

    def test_ipv6_is_accepted(self, proxy_depth):
        proxy_depth(1)
        assert resolve_client_ip(make_request(forwarded="2001:db8::1")) == "2001:db8::1"


class TestIdentity:
    def test_authenticated_user_buckets_by_id_not_ip(self, proxy_depth):
        """An authenticated caller cannot escape their bucket by changing IP."""
        proxy_depth(1)
        request = make_request(forwarded=REAL_CLIENT, user_id="user-123")
        assert _identity(request) == "user:user-123"

    def test_anonymous_caller_buckets_by_ip(self, proxy_depth):
        proxy_depth(1)
        assert _identity(make_request(forwarded=REAL_CLIENT)) == f"ip:{REAL_CLIENT}"

    def test_forged_header_cannot_rotate_the_anonymous_bucket(self, proxy_depth):
        """The whole point: two forged headers must land in one bucket."""
        proxy_depth(1)
        first = _identity(make_request(forwarded=f"{FORGED}, {REAL_CLIENT}"))
        second = _identity(make_request(forwarded=f"8.8.8.8, {REAL_CLIENT}"))
        assert first == second == f"ip:{REAL_CLIENT}"


class TestBucketKeyIntegrity:
    """The resolved value ends up inside a Redis key, so it has to stay clean."""

    def test_resolved_value_is_always_an_ip_or_the_constant(self, proxy_depth):
        proxy_depth(1)
        hostile = [
            "ratelimit:auth:ip:1.2.3.4",  # attempts to collide with another key
            "1.2.3.4\r\nSET foo bar",  # CRLF injection
            "1.2.3.4 1.2.3.5",
            "*",
        ]
        for value in hostile:
            resolved = resolve_client_ip(make_request(forwarded=value))
            assert resolved == SOCKET_IP, value

    def test_bucket_key_shape_is_stable(self, proxy_depth):
        """Guards the format the Redis key is built from."""
        proxy_depth(1)
        identity = _identity(make_request(forwarded=REAL_CLIENT))
        assert identity == f"ip:{REAL_CLIENT}"
        assert "\n" not in identity and "\r" not in identity and " " not in identity
