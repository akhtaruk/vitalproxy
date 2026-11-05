#!/usr/bin/env python3
"""Build an offline installation guide with embedded downloadable source."""
import base64
import hashlib
import html
import io
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT.parent / "generated-artifacts"
NAMES = (
    "README.md", "config.example.json", "sbc.py", "install.sh",
    "install-local.sh", "install-remote.sh", "status.sh", "rollback.sh",
    "build_download.py", "templates/kamailio.cfg", "templates/rtpengine.conf",
    "templates/firewall-local.nft", "templates/firewall-remote.nft",
)


def main():
    OUT.mkdir(exist_ok=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in NAMES:
            archive.write(ROOT / name, "sbc/" + name)
    payload = buffer.getvalue()
    (OUT / "local-network-sbc.zip").write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    encoded = base64.b64encode(payload).decode()
    source = []
    for name in NAMES:
        text = (ROOT / name).read_text()
        mime = "application/octet-stream"
        data = base64.b64encode(text.encode()).decode()
        source.append(
            f'<details><summary>{html.escape(name)}</summary>'
            f'<p><a class="small" href="data:{mime};base64,{data}" '
            f'download="{html.escape(pathlib.Path(name).name)}">Download this file</a></p>'
            f'<pre>{html.escape(text)}</pre></details>'
        )
    readme = html.escape((ROOT / "README.md").read_text())
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Local Network SIP SBC — Scripts &amp; Installation Guide</title>
<style>
:root{{color-scheme:light;--ink:#152e40;--accent:#075e60;--muted:#476276}}
*{{box-sizing:border-box}}body{{margin:0;background:#edf3f3;color:var(--ink);
font:16px/1.65 system-ui,sans-serif}}main{{max-width:1000px;margin:auto;padding:40px 24px 80px}}
header{{border-top:5px solid var(--accent);padding:28px;background:#fff;border-radius:8px}}
.label{{font:600 12px/1.5 system-ui;letter-spacing:.13em;text-transform:uppercase;color:var(--accent)}}
h1{{font-size:clamp(28px,5vw,42px);line-height:1.15;margin:12px 0}}h2{{margin-top:32px}}
p{{max-width:78ch}}a{{color:var(--accent)}}.button{{display:inline-block;background:var(--accent);
color:white;text-decoration:none;padding:12px 20px;border-radius:5px;font-weight:650}}
.small{{font-size:14px}}.notice{{border-left:4px solid #b87413;background:#fff7e6;padding:16px 20px;margin:24px 0}}
section{{background:#fff;padding:24px 28px;margin-top:20px;border-radius:8px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#102c3a;color:#e2eef4;
padding:20px;border-radius:5px;font:13px/1.65 ui-monospace,monospace}}
code{{font-family:ui-monospace,monospace}}summary{{cursor:pointer;font-weight:650;padding:14px 0}}
details{{border-bottom:1px solid #cfdddd}}.checksum{{font-size:12px;overflow-wrap:anywhere;color:var(--muted)}}
li{{margin:8px 0}}footer{{font-size:13px;color:var(--muted);margin-top:24px}}
@media print{{body{{background:white}}main{{padding:0}}details pre{{display:block}}.button{{color:black;background:none}}}}
</style></head><body><main>
<header><div class="label">Self-managed Linux appliance · First version</div>
<h1>Local Network SIP SBC</h1>
<p>Connect local SIP phones to your remote Asterisk or VitalPBX server using
WireGuard, Kamailio and RTPengine. All installation scripts and source are included.</p>
<a class="button" download="local-network-sbc.zip"
href="data:application/zip;base64,{encoded}">Download all scripts (.zip)</a>
<p class="checksum">ZIP SHA-256: {digest}</p></header>
<div class="notice"><strong>Read before installation.</strong> This version targets dedicated
Debian 12 / Ubuntu 24.04 devices and PJSIP with Path support. It has not been tested with
your PBX or phones. Validate registration, incoming calls and two-way audio in a lab before
production use. The full guide below covers required PBX routing and firewall changes.</div>
<section><h2>Deployment</h2>
<pre>Phones → Local SBC ═══ encrypted WireGuard tunnel ═══ Remote gateway → PBX
         Kamailio + RTPengine                       separate Linux device</pre>
<p>Keep the remote gateway separate from your existing PBX installation.
The SBC does not replace your PBX or store extension passwords. No hosted web service is needed.</p>
<h2>Start here</h2><ol>
<li>Download and extract the ZIP. Copy the complete <code>sbc</code> directory to both devices.</li>
<li>Run the preparation commands below. Exchange only the printed <strong>public</strong> keys.</li>
<li>Copy <code>config.example.json</code> to <code>config.json</code> on each device.
Enter your site addresses and the <em>other</em> device's public key.</li>
<li>Install the remote gateway first, then the local SBC.</li>
<li>Apply the return route, PJSIP Path/direct-media settings and firewall rules from the full guide.
Set your test phone's outbound proxy to the SBC.</li></ol>
<h3>Remote gateway</h3><pre>cd sbc
sudo bash install-remote.sh prepare
cp config.example.json config.json
nano config.json
sudo bash install-remote.sh install config.json</pre>
<h3>Local SBC</h3><pre>cd sbc
sudo bash install-local.sh prepare
cp config.example.json config.json
nano config.json
sudo bash install-local.sh install config.json</pre>
<p>Prepare <em>both</em> devices before editing peer keys and running install.
Never share the private keys. The tunnel encrypts traffic between sites, not the two LAN segments.</p>
<h3>Check status / rollback</h3>
<pre>sudo bash status.sh
# Disconnects calls and removes the managed tunnel/configuration:
sudo bash rollback.sh --confirm</pre></section>
<section><h2>Complete installation guide</h2>
<p>This same guide is included as <code>sbc/README.md</code> in the ZIP.</p>
<pre>{readme}</pre></section>
<section><h2>Every script and configuration file</h2>
<p>Expand to inspect the source or download individual files. Use the ZIP for installation:
the scripts require the templates and renderer together.</p>{''.join(source)}</section>
<footer>Offline, self-contained guide. No tracking, external resources or credentials.
The ZIP contains source files and example configuration only.</footer>
</main></body></html>"""
    destination = OUT / "sbc-installation-guide.html"
    destination.write_text(page)
    print(f"Guide: {destination.relative_to(ROOT.parent)}")
    print(f"ZIP: generated-artifacts/local-network-sbc.zip ({len(payload)} bytes)")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
