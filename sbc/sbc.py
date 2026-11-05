#!/usr/bin/env python3
"""Offline renderer for a single-site SIP edge. No credentials in JSON."""
import argparse
import base64
import ipaddress
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
FIELDS = set(json.loads((ROOT / "config.example.json").read_text()))


def validate(config, require_peer=True):
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object")
    if set(config) != FIELDS:
        raise ValueError(f"Missing fields: {sorted(FIELDS - set(config))}; "
                         f"unknown fields: {sorted(set(config) - FIELDS)}")
    c = config.copy()
    for name in ("lan_ip", "pbx_ip", "gateway_lan_ip",
                 "local_tunnel_ip", "remote_tunnel_ip"):
        address = ipaddress.IPv4Address(c[name])
        if address.is_multicast or address.is_unspecified or address.is_loopback or address.is_reserved:
            raise ValueError(f"{name} must be a usable unicast IPv4 address")
        c[name] = str(address)
    lan = ipaddress.IPv4Network(c["lan_cidr"], strict=True)
    if lan.prefixlen < 16 or lan.prefixlen > 30:
        raise ValueError("lan_cidr must be /16 through /30; use a dedicated voice LAN")
    if ipaddress.IPv4Address(c["lan_ip"]) not in lan.hosts():
        raise ValueError("lan_ip must be a host in lan_cidr")
    c["lan_cidr"] = str(lan)
    for field in ("pbx_ip", "gateway_lan_ip", "local_tunnel_ip", "remote_tunnel_ip"):
        if ipaddress.IPv4Address(c[field]) in lan:
            raise ValueError(f"{field} overlaps the phone LAN; renumber before installation")
    if len({c[k] for k in ("lan_ip", "pbx_ip", "gateway_lan_ip",
                          "local_tunnel_ip", "remote_tunnel_ip")}) != 5:
        raise ValueError("All five device/interface addresses must be different")
    for field in ("pbx_sip_port", "wireguard_port", "sbc_sip_port",
                  "pbx_rtp_min", "pbx_rtp_max", "sbc_rtp_min", "sbc_rtp_max"):
        if type(c[field]) is not int or not 1024 <= c[field] <= 65535:
            raise ValueError(f"{field} must be an integer from 1024 to 65535")
    for prefix in ("sbc", "pbx"):
        if c[f"{prefix}_rtp_max"] - c[f"{prefix}_rtp_min"] < 99:
            raise ValueError(f"{prefix} RTP range needs at least 100 ports")
        if c[f"{prefix}_rtp_min"] <= c[f"{prefix}_sip_port"] <= c[f"{prefix}_rtp_max"]:
            raise ValueError(f"{prefix} SIP port overlaps RTP range")
    if (c["sbc_sip_port"] == c["wireguard_port"] or
            c["sbc_rtp_min"] <= c["wireguard_port"] <= c["sbc_rtp_max"]):
        raise ValueError("WireGuard port overlaps local SIP/RTP ports")
    if type(c["mtu"]) is not int or not 1280 <= c["mtu"] <= 1420:
        raise ValueError("mtu must be an integer from 1280 to 1420")
    endpoint = c["remote_endpoint"]
    if not isinstance(endpoint, str) or len(endpoint) > 253:
        raise ValueError("remote_endpoint must be a hostname or IPv4 address")
    if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", endpoint):
        raise ValueError("Invalid remote endpoint; no URL, port, or IPv6 in this release")
    if any(not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?", p)
           for p in endpoint.split(".")):
        raise ValueError("Invalid endpoint hostname")
    if endpoint in (c["pbx_ip"], c["local_tunnel_ip"], c["remote_tunnel_ip"]):
        raise ValueError("Public tunnel endpoint must not match a tunnel-routed address")
    if (c["sbc_sip_port"] == 2223 or c["wireguard_port"] == 2223 or
            c["sbc_rtp_min"] <= 2223 <= c["sbc_rtp_max"]):
        raise ValueError("SIP/RTP/WireGuard ports must not overlap control port 2223")
    if require_peer:
        key = c["peer_public_key"]
        try:
            raw = base64.b64decode(key, validate=True)
        except (ValueError, TypeError) as e:
            raise ValueError("peer_public_key must be the other device's WireGuard public key") from e
        if len(raw) != 32 or base64.b64encode(raw).decode() != key or raw == bytes(32):
            raise ValueError("Invalid WireGuard public key")
    return c


def substitute(text, c):
    return re.sub(r"@@([a-z_]+)@@", lambda match: str(c[match[1]]), text)


def files_for(c, role, private_key):
    if role == "local":
        address, peer = c["local_tunnel_ip"], c["remote_tunnel_ip"]
        allowed = f'{peer}/32, {c["pbx_ip"]}/32'
        endpoint = f'Endpoint = {c["remote_endpoint"]}:{c["wireguard_port"]}\nPersistentKeepalive = 25\n'
    else:
        address, peer = c["remote_tunnel_ip"], c["local_tunnel_ip"]
        allowed = f"{peer}/32"
        endpoint = ""
    wg = (f'[Interface]\nAddress = {address}/32\nPrivateKey = {private_key}\n'
          f'ListenPort = {c["wireguard_port"]}\nMTU = {c["mtu"]}\n\n'
          f'[Peer]\nPublicKey = {c["peer_public_key"]}\nAllowedIPs = {allowed}\n{endpoint}')
    result = {"wg-sbc.conf": wg}
    for name in (f"firewall-{role}.nft",):
        result["firewall.nft"] = substitute((ROOT / "templates" / name).read_text(), c)
    if role == "local":
        result["kamailio.cfg"] = substitute((ROOT / "templates/kamailio.cfg").read_text(), c)
        result["rtpengine.conf"] = substitute((ROOT / "templates/rtpengine.conf").read_text(), c)
    else:
        result["90-sbc-forward.conf"] = "net.ipv4.ip_forward = 1\n"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "render", "get"))
    parser.add_argument("--config", required=True, type=pathlib.Path)
    parser.add_argument("--role", choices=("local", "remote"))
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--private-key-file", type=pathlib.Path)
    parser.add_argument("--field", choices=sorted(FIELDS))
    parser.add_argument("--allow-unpaired", action="store_true")
    args = parser.parse_args()
    try:
        if args.allow_unpaired and args.action != "validate":
            raise ValueError("--allow-unpaired is only available for validate")
        c = validate(json.loads(args.config.read_text()), not args.allow_unpaired)
        if args.action == "validate":
            print("Configuration valid" + ("; peer key not checked" if args.allow_unpaired else ""))
        elif args.action == "get":
            if not args.field:
                raise ValueError("get requires --field")
            print(c[args.field])
        else:
            if not args.role or not args.output or not args.private_key_file:
                raise ValueError("render needs --role, --output, and --private-key-file")
            # Private keys are read only on the appliance, never sent to a server.
            key = args.private_key_file.read_text().strip()
            raw = base64.b64decode(key, validate=True)
            if len(raw) != 32 or base64.b64encode(raw).decode() != key or raw == bytes(32):
                raise ValueError("Invalid private key file")
            args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
            for name, text in files_for(c, args.role, key).items():
                path = args.output / name
                path.write_text(text)
                path.chmod(0o600)
            print(f"Rendered {args.role} files in {args.output}; contains a private key, keep private")
    except (ValueError, OSError, TypeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
