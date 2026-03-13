#!/usr/bin/env python3
"""Live Proxy Listener for CSRF Shield AI.

Captures live web traffic through a Mitmproxy add-on and saves it
out to .har format, which can immediately be loaded into the Go TUI
or web dashboard.

Ref:
    - docs/proposal/PROPOSAL.md
"""

import os
import argparse
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from mitmproxy.addons import hardump  # Mitmproxy includes a built-in HAR dumper plugin

def start_proxy(host: str, port: int, output_file: str):
    print(f"[*] Starting CSRF Shield Live Capture Proxy at {host}:{port}")
    print(f"[*] Capturing to {output_file} ... Press Ctrl+C to stop.")
    options = Options(listen_host=host, listen_port=port)
    m = DumpMaster(options, with_termlog=False, with_dumper=False)
    
    # Attach HAR dump addon
    har_addon = hardump.Hardump()
    har_addon.configure(["hardump=" + output_file])
    m.addons.add(har_addon)

    try:
        m.run()
    except KeyboardInterrupt:
        print("\n[*] Capture finished.")
    finally:
        m.shutdown()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live traffic capture -> HAR file")
    parser.add_argument("--host", default="127.0.0.1", help="Proxy listen host")
    parser.add_argument("--port", type=int, default=8080, help="Proxy listen port")
    parser.add_argument("--out", default="live_capture.har", help="Output HAR file")
    args = parser.parse_args()
    
    # Pre-create empty file for the addon or clear existing
    with open(args.out, "w") as f:
        pass
        
    start_proxy(args.host, args.port, args.out)
