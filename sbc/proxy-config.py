#!/usr/bin/env python3
"""Validate and render a single-host LAN SIP outbound proxy."""
import argparse
import ipaddress
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
FIELDS = set(json.loads((ROOT / "config.example.json").read_text()))


def validate(config):
    if not isinstance(config, dict) or set(config) != FIELDS:
        missing = sorted(FIELDS - set(config)) if isinstance(config, dict) else sorted(FIELDS)
        extra = sorted(set(config) - FIELDS) if isinstance(config, dict) else []
        raise ValueError(f"Invalid fields; missing={missing}, unknown={extra}")
    for field in ("proxy_ip", "pbx_ip"):
        address = ipaddress.ip_address(config[field])
        if address.version != 4 or address.is_unspecified or address.is_multicast or address.is_loopback:
            raise ValueError(f"{field} must be a usable IPv4 address")
    lan = ipaddress.ip_network(config["lan_cidr"], strict=True)
    if lan.version != 4 or not 16 <= lan.prefixlen <= 30:
        raise ValueError("lan_cidr must be an IPv4 network from /16 through /30")
    if ipaddress.ip_address(config["proxy_ip"]) not in lan:
        raise ValueError("proxy_ip must be inside lan_cidr")
    for field in ("pbx_sip_port", "proxy_port"):
        if type(config[field]) is not int or not 1024 <= config[field] <= 65535:
            raise ValueError(f"{field} must be an integer from 1024 to 65535")
    return {**config, "lan_cidr": str(lan)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "render"))
    parser.add_argument("--config", required=True, type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    try:
        c = validate(json.loads(args.config.read_text()))
        if args.action == "validate":
            print("Proxy configuration valid")
            return 0
        if not args.output:
            raise ValueError("render requires --output")
        kamailio = (ROOT / "templates/kamailio-proxy.cfg").read_text()
        nft = (ROOT / "templates/firewall-proxy.nft").read_text()
        for key, value in c.items():
            kamailio = kamailio.replace(f"@@{key}@@", str(value))
            nft = nft.replace(f"@@{key}@@", str(value))
        if re.search(r"@@[a-z_]+@@", kamailio + nft):
            raise ValueError("Internal template contains an unknown field")
        if args.output.exists():
            raise ValueError(f"Output directory already exists: {args.output}")
        args.output.mkdir(parents=True, mode=0o700)
        (args.output / "kamailio.cfg").write_text(kamailio)
        (args.output / "firewall.nft").write_text(nft)
        print(f"Rendered outbound proxy configuration to {args.output}")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
