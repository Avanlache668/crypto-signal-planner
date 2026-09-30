#!/usr/bin/env python3
import hashlib
import hmac
from gate_client import GateClient, GateConfig, LiveTradingBlocked


def test_sign():
    method = "GET"
    path = "/api/v4/spot/accounts"
    query = "currency=USDT"
    body = ""
    secret = "secret"
    ts = "1700000000"
    payload_hash = hashlib.sha512(b"").hexdigest()
    expected = hmac.new(secret.encode(), f"{method}\n{path}\n{query}\n{payload_hash}\n{ts}".encode(), hashlib.sha512).hexdigest()
    assert GateClient.sign(method, path, query, body, secret, ts) == expected


def test_preview():
    p = GateClient.preview_limit_order("BTC_USDT", "buy", "0.001", "50000")
    assert p["account"] == "spot"
    assert p["auto_borrow"] is False
    assert p["type"] == "limit"


def test_live_block():
    client = GateClient(GateConfig(mode="live-readonly", api_key="x", api_secret="y", host="https://api.gateio.ws"))
    try:
        client.submit_testnet_limit_order("BTC_USDT", "buy", "0.001", "50000")
    except LiveTradingBlocked:
        pass
    else:
        raise AssertionError("live trading guard did not fire")


def test_testnet_host_guard():
    client = GateClient(GateConfig(mode="testnet", api_key="x", api_secret="y", host="https://example.com"))
    try:
        client.submit_testnet_limit_order("BTC_USDT", "buy", "0.001", "50000")
    except LiveTradingBlocked:
        pass
    else:
        raise AssertionError("non-official testnet host guard did not fire")


if __name__ == "__main__":
    test_sign(); test_preview(); test_live_block(); test_testnet_host_guard()
    print("gate client tests: PASS")
