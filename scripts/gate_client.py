#!/usr/bin/env python3
"""Minimal Gate API v4 client with a hard live-trading block.

Capabilities:
- Public spot ticker reads.
- Authenticated spot account reads.
- Deterministic order preview.
- Actual order submission ONLY against Gate TestNet.

No withdrawals, transfers, margin, futures, or live-money order submission are implemented.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API_PREFIX = "/api/v4"
DEFAULT_LIVE_HOST = "https://api.gateio.ws"
DEFAULT_TESTNET_HOST = "https://api-testnet.gateapi.io"


class GateAPIError(RuntimeError):
    pass


class LiveTradingBlocked(GateAPIError):
    pass


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _decimal_str(value: str | int | float | Decimal) -> str:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid decimal value: {value}") from exc
    if d <= 0:
        raise ValueError("numeric values must be > 0")
    return format(d, "f")


@dataclass(frozen=True)
class GateConfig:
    mode: str = "live-readonly"  # live-readonly | testnet
    api_key: str = ""
    api_secret: str = ""
    host: str = ""
    timeout: int = 15

    @classmethod
    def from_env(cls) -> "GateConfig":
        mode = os.getenv("GATE_MODE", "live-readonly").strip().lower()
        if mode not in {"live-readonly", "testnet"}:
            raise ValueError("GATE_MODE must be live-readonly or testnet")
        default_host = DEFAULT_TESTNET_HOST if mode == "testnet" else DEFAULT_LIVE_HOST
        host = os.getenv("GATE_HOST", default_host).rstrip("/")
        return cls(
            mode=mode,
            api_key=os.getenv("GATE_API_KEY", ""),
            api_secret=os.getenv("GATE_API_SECRET", ""),
            host=host,
            timeout=int(os.getenv("GATE_TIMEOUT", "15")),
        )


class GateClient:
    def __init__(self, config: GateConfig):
        self.config = config

    @staticmethod
    def sign(method: str, path: str, query_string: str, payload_string: str,
             api_secret: str, timestamp: str) -> str:
        payload_hash = hashlib.sha512((payload_string or "").encode("utf-8")).hexdigest()
        sign_string = "\n".join([
            method.upper(), path, query_string or "", payload_hash, timestamp
        ])
        return hmac.new(
            api_secret.encode("utf-8"), sign_string.encode("utf-8"), hashlib.sha512
        ).hexdigest()

    def _headers(self, method: str, path: str, query: str, body: str,
                 authenticated: bool) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if not authenticated:
            return headers
        if not self.config.api_key or not self.config.api_secret:
            raise GateAPIError("GATE_API_KEY and GATE_API_SECRET are required for private endpoints")
        ts = str(int(time.time()))
        headers.update({
            "KEY": self.config.api_key,
            "Timestamp": ts,
            "SIGN": self.sign(method, path, query, body, self.config.api_secret, ts),
        })
        return headers

    def _request(self, method: str, endpoint: str,
                 query_pairs: Iterable[tuple[str, str]] = (),
                 payload: dict[str, Any] | None = None,
                 authenticated: bool = False) -> Any:
        path = API_PREFIX + endpoint
        query = urlencode(list(query_pairs))
        body = _json_dumps(payload) if payload is not None else ""
        url = f"{self.config.host}{path}" + (f"?{query}" if query else "")
        req = Request(
            url,
            data=body.encode("utf-8") if payload is not None else None,
            headers=self._headers(method, path, query, body, authenticated),
            method=method.upper(),
        )
        try:
            with urlopen(req, timeout=self.config.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise GateAPIError(f"Gate HTTP {exc.code}: {raw[:1000]}") from exc
        except URLError as exc:
            raise GateAPIError(f"Gate network error: {exc}") from exc

    def ticker(self, currency_pair: str) -> Any:
        return self._request("GET", "/spot/tickers", [("currency_pair", currency_pair)])

    def spot_accounts(self, currency: str | None = None) -> Any:
        pairs = [("currency", currency)] if currency else []
        return self._request("GET", "/spot/accounts", pairs, authenticated=True)

    @staticmethod
    def preview_limit_order(currency_pair: str, side: str, amount: Any, price: Any,
                            client_tag: str = "t-crypto-signal") -> dict[str, Any]:
        side = side.lower()
        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        if not currency_pair or "_" not in currency_pair:
            raise ValueError("currency_pair must look like BTC_USDT")
        if not client_tag.startswith("t-"):
            raise ValueError("client_tag must start with t-")
        return {
            "text": client_tag[:30],
            "currency_pair": currency_pair,
            "type": "limit",
            "account": "spot",
            "side": side,
            "amount": _decimal_str(amount),
            "price": _decimal_str(price),
            "time_in_force": "gtc",
            "auto_borrow": False,
        }

    def submit_testnet_limit_order(self, currency_pair: str, side: str, amount: Any,
                                   price: Any, client_tag: str = "t-crypto-signal") -> Any:
        if self.config.mode != "testnet":
            raise LiveTradingBlocked(
                "Live-money order submission is intentionally blocked. Set GATE_MODE=testnet to test order execution."
            )
        if self.config.host.rstrip("/") != DEFAULT_TESTNET_HOST:
            raise LiveTradingBlocked(
                "Test order execution is allowed only against the official Gate TestNet host."
            )
        payload = self.preview_limit_order(currency_pair, side, amount, price, client_tag)
        return self._request("POST", "/spot/orders", payload=payload, authenticated=True)


def _main() -> int:
    ap = argparse.ArgumentParser(description="Gate API v4 safe bridge (live-readonly, testnet trading only)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("ticker")
    t.add_argument("pair")

    b = sub.add_parser("balances")
    b.add_argument("--currency")

    p = sub.add_parser("preview")
    p.add_argument("pair")
    p.add_argument("side", choices=["buy", "sell"])
    p.add_argument("amount")
    p.add_argument("price")

    o = sub.add_parser("testnet-order")
    o.add_argument("pair")
    o.add_argument("side", choices=["buy", "sell"])
    o.add_argument("amount")
    o.add_argument("price")

    args = ap.parse_args()
    client = GateClient(GateConfig.from_env())
    if args.cmd == "ticker":
        result = client.ticker(args.pair)
    elif args.cmd == "balances":
        result = client.spot_accounts(args.currency)
    elif args.cmd == "preview":
        result = client.preview_limit_order(args.pair, args.side, args.amount, args.price)
    else:
        result = client.submit_testnet_limit_order(args.pair, args.side, args.amount, args.price)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
