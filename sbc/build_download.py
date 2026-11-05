#!/usr/bin/env python3
"""Build a self-contained download guide and ZIP for the one-machine LAN proxy."""
import base64
import hashlib
import html
import io
import pathlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT.parent / "generated-artifacts"
NAMES = (
    "README.md", "config.example.json", "proxy-config.py", "install-proxy.sh",
    "status-proxy.sh", "rollback-proxy.sh", "build_download.py",
    "templates/kamailio-proxy.cfg", "templates/firewall-proxy.nft",
)


def main():
    kamailio = shutil.which("kamailio")
    if not kamailio:
        raise SystemExit("Kamailio is required to validate the config before building the ZIP.")
    with tempfile.TemporaryDirectory(prefix="sbc-proxy-check-") as temporary:
        rendered = pathlib.Path(temporary) / "rendered"
        subprocess.run([
            sys.executable, str(ROOT / "proxy-config.py"), "render",
            "--config", str(ROOT / "config.example.json"), "--output", str(rendered),
        ], check=True)
        subprocess.run([kamailio, "-c", "-f", str(rendered / "kamailio.cfg")], check=True)
    OUT.mkdir(exist_ok=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in NAMES:
            archive.write(ROOT / name, "sbc/" + name)
    payload = buffer.getvalue()
    (OUT / "vitalpbx-lan-outbound-proxy.zip").write_bytes(payload)
    old_zip = OUT / "local-network-sbc.zip"
    if old_zip.exists():
        old_zip.unlink()
    digest = hashlib.sha256(payload).hexdigest()
    encoded = base64.b64encode(payload).decode()
    readme = html.escape((ROOT / "README.md").read_text())
    source = []
    for name in NAMES:
        text = (ROOT / name).read_text()
        encoded_source = base64.b64encode(text.encode()).decode()
        source.append(
            f'<details><summary>{html.escape(name)}</summary>'
            f'<p><a href="data:application/octet-stream;base64,{encoded_source}" '
            f'download="{html.escape(pathlib.Path(name).name)}">Download this file</a></p>'
            f'<pre>{html.escape(text)}</pre></details>'
        )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VitalPBX LAN SIP Outbound Proxy</title>
<style>
:root{{color-scheme:light;--ink:#193246;--accent:#075e60;--muted:#526d7b}}
*{{box-sizing:border-box}}body{{margin:0;background:#edf3f3;color:var(--ink);
font:16px/1.65 system-ui,sans-serif}}main{{max-width:920px;margin:auto;padding:38px 22px 72px}}
header,section{{background:white;padding:24px 30px;margin:18px 0;border-radius:8px}}
header{{border-top:5px solid var(--accent)}}h1{{font-size:clamp(28px,5vw,40px);line-height:1.15}}
h2{{margin-top:30px}}.label{{text-transform:uppercase;letter-spacing:.12em;color:var(--accent);font-size:12px;font-weight:700}}
.button{{display:inline-block;background:var(--accent);color:white;text-decoration:none;
padding:12px 19px;border-radius:5px;font-weight:700}}
.note{{background:#fff6df;border-left:4px solid #b87413;padding:14px 18px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#102c3a;color:#e4eff3;
padding:18px;border-radius:5px;font:13px/1.6 ui-monospace,monospace}}
summary{{cursor:pointer;padding:12px 0;font-weight:650}}details{{border-bottom:1px solid #d7e1e1}}
.small{{font-size:12px;color:var(--muted);overflow-wrap:anywhere}}li{{margin:8px 0}}
</style></head><body><main>
<header><div class="label">One Debian 13 machine · No VPN · No gateway</div>
<h1>VitalPBX LAN SIP Outbound Proxy</h1>
<p>Install a simple Kamailio SIP proxy on your local LAN. Phones send SIP
signalling through it to VitalPBX. Call audio remains direct.</p>
<a class="button" download="vitalpbx-lan-outbound-proxy.zip"
href="data:application/zip;base64,{encoded}">Download the Debian 13 script ZIP</a>
<p class="small">SHA-256: {digest}</p></header>
<section><p class="note"><strong>Scope:</strong> one Debian 13 box. No VPN, no second gateway,
and no software installation on VitalPBX. This is an outbound SIP proxy, not a media relay:
audio and incoming calls are not handled by this version.</p>
<h2>Quick start</h2>
<ol><li>Download and extract the ZIP onto your Debian 13 machine.</li>
<li>Open a terminal in its <code>sbc</code> folder.</li>
<li>Set the Debian IP, phone LAN subnet and reachable VitalPBX IP in the config.</li>
<li>Install the proxy and set one phone's outbound proxy to the Debian IP.</li></ol>
<pre>cp config.example.json config.json
nano config.json
python3 proxy-config.py validate --config config.json
sudo bash install-proxy.sh install config.json
sudo bash status-proxy.sh</pre>
<h3>Phone setting</h3><p>Keep its registrar, domain and credentials pointed at VitalPBX.
Set the separate outbound proxy to the Debian IP and UDP port, for example
<code>192.168.50.10:5060</code>.</p>
<h2>Full setup and limitations</h2><pre>{readme}</pre></section>
<section><h2>Download individual scripts or inspect source</h2>{''.join(source)}</section>
</main></body></html>"""
    guide = OUT / "vitalpbx-lan-outbound-proxy.html"
    guide.write_text(page)
    print(f"Guide: {guide.relative_to(ROOT.parent)}")
    print(f"ZIP: generated-artifacts/vitalpbx-lan-outbound-proxy.zip ({len(payload)} bytes)")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
