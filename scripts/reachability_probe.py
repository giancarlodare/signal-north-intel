"""Reachability diagnostic for the coverage report's unreachable(ConnectionError)
class. Read-only network probe; writes nothing, no Supabase, no LLM.

The question (operator 2026-08-02): CITT, SSHRC, CIHR and AG Ontario load in
a browser but died at connection level from the CI runner. Is that the UA,
the egress, or genuinely per-host? If systemic, worklist items 14-29 and the
coverage report's "unreachable" rows are largely false negatives.

Method: each host is tested layer by layer so the failure names its own
class instead of collapsing into requests.ConnectionError:

  DNS -> TCP connect -> TLS handshake -> HTTP GET (three UAs) -> curl GET

Layer semantics for the verdict:
  * DNS/TCP/TLS failure happens before any header is sent, so a failure
    there can NEVER be the User-Agent. That is IP/edge or TLS-fingerprint
    territory.
  * requests fails TLS but curl succeeds  -> client TLS fingerprint block
    (python/urllib3 handshake refused, curl's accepted).
  * honest UA gets 403 but browser UA 200 -> UA-based bot filter. Per the
    operator's discipline that is a BOUNDARY WE REPORT, not one we evade:
    the browser UA below exists for this diagnosis only and is never used
    for collection.
  * controls fail too -> the runner egress itself, not these hosts.

Extra hosts can be appended as argv, so re-testing the rest of the worklist
is a dispatch, not a code change.
"""
import socket
import ssl
import subprocess
import sys

import requests

TIMEOUT = 12

# Identical string to coverage_probe.py, so results are comparable.
UA_HONEST = "SignalNorthIntel/1.0"
# DIAGNOSIS ONLY (operator authorization 2026-08-02): sent to distinguish a
# UA-based filter from an edge/TLS block. Never used by any collector; a host
# that only serves this UA is reported as a deliberate bot boundary.
UA_BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# Hosts exactly as they appear in the coverage_probe rosters.
AFFECTED = [
    ("CITT", "www.citt-tcce.gc.ca"),
    ("SSHRC", "www.sshrc-crsh.gc.ca"),
    ("CIHR", "cihr-irsc.gc.ca"),
    ("AG Ontario", "www.auditor.on.ca"),
    ("Esprit de Corps", "espritdecorps.ca"),
    ("UCCM Police", "www.uccmpolice.com"),
]
CONTROLS = [
    ("CONTROL CanadaBuys (collected nightly)", "canadabuys.canada.ca"),
    ("CONTROL canada.ca", "www.canada.ca"),
    ("CONTROL ontario.ca", "www.ontario.ca"),
    ("CONTROL AG Canada (gc.ca sibling)", "www.oag-bvg.gc.ca"),
]

EDGE_HEADERS = ("server", "cf-ray", "x-amz-cf-id", "x-cache", "via",
                "x-served-by", "x-akamai-transformed")


def layer_probe(host: str) -> dict:
    """DNS, TCP, TLS -- the pre-HTTP layers, reported separately."""
    out: dict = {"dns": None, "tcp": None, "tls": None}
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        out["dns"] = sorted({i[4][0] for i in infos})
    except OSError as e:
        out["dns_err"] = f"{type(e).__name__}: {e}"
        return out
    try:
        sock = socket.create_connection((host, 443), timeout=TIMEOUT)
        out["tcp"] = "connected"
    except OSError as e:
        out["tcp_err"] = f"{type(e).__name__}: {e}"
        return out
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
            issuer = dict(x[0] for x in cert.get("issuer", ())) if cert else {}
            out["tls"] = {"version": tls.version(),
                          "issuer": issuer.get("organizationName", "?")}
    except (ssl.SSLError, OSError) as e:
        out["tls_err"] = f"{type(e).__name__}: {e}"
    finally:
        sock.close()
    return out


def http_get(host: str, ua: str | None, path: str = "/") -> str:
    headers = {"User-Agent": ua} if ua else {}
    try:
        r = requests.get(f"https://{host}{path}", headers=headers,
                         timeout=TIMEOUT, allow_redirects=True)
        edge = {k: r.headers[k] for k in EDGE_HEADERS if k in r.headers}
        note = f" edge={edge}" if edge else ""
        loc = f" -> {r.url}" if r.url.rstrip("/") != f"https://{host}{path}".rstrip("/") else ""
        return f"HTTP {r.status_code}{loc}{note}"
    except requests.RequestException as e:
        cause = e.__cause__ or e
        return f"FAIL {type(cause).__name__}: {str(cause)[:160]}"


def curl_get(host: str) -> str:
    """Same GET via curl: a different TLS fingerprint than python/urllib3.
    Divergence from the requests result is the fingerprint-block signature."""
    try:
        p = subprocess.run(
            ["curl", "-sS", "-o", "/dev/null", "-A", UA_HONEST, "--max-time",
             str(TIMEOUT), "-w", "%{http_code} remote=%{remote_ip}",
             f"https://{host}/"],
            capture_output=True, text=True, timeout=TIMEOUT + 5)
        if p.returncode == 0:
            return f"HTTP {p.stdout.strip()}"
        return f"FAIL exit={p.returncode}: {(p.stderr or p.stdout).strip()[:160]}"
    except (subprocess.SubprocessError, OSError) as e:
        return f"FAIL {type(e).__name__}: {e}"


def classify(layers: dict, honest: str, browser: str, curl: str) -> str:
    if "dns_err" in layers:
        return "DNS -- host does not resolve from this egress (UA irrelevant)"
    if "tcp_err" in layers:
        return "TCP -- blocked before any header is sent (UA irrelevant; IP/edge)"
    if "tls_err" in layers:
        if curl.startswith("HTTP"):
            return "TLS FINGERPRINT -- python handshake refused, curl accepted"
        return "TLS -- handshake refused for both clients (edge-level)"
    h_ok, b_ok = honest.startswith("HTTP 2"), browser.startswith("HTTP 2")
    if h_ok:
        return "REACHABLE with honest UA -- coverage row was a false negative"
    if b_ok and not h_ok:
        return ("UA FILTER -- serves browsers, refuses identified bots: "
                "a deliberate boundary, report it, do not evade it")
    return f"HTTP-level failure under every UA (honest={honest[:40]})"


def main() -> int:
    extra = [(f"argv:{h}", h) for h in sys.argv[1:]]
    print("REACHABILITY PROBE -- read-only; browser UA is diagnosis-only")
    print(f"vantage: this runner; timeout {TIMEOUT}s per attempt\n")

    verdicts = []
    for label, host in AFFECTED + extra + CONTROLS:
        print(f"{label} ({host})")
        layers = layer_probe(host)
        if layers.get("dns"):
            print(f"  dns   {', '.join(layers['dns'][:4])}")
        for k in ("dns_err", "tcp_err", "tls_err"):
            if k in layers:
                print(f"  {k[:3]}   {layers[k]}")
        if layers.get("tls"):
            print(f"  tls   {layers['tls']['version']} "
                  f"issuer={layers['tls']['issuer']}")
        honest = http_get(host, UA_HONEST)
        default = http_get(host, None)
        browser = http_get(host, UA_BROWSER)
        curl = curl_get(host)
        print(f"  GET honest-UA   {honest}")
        print(f"  GET default-UA  {default}")
        print(f"  GET browser-UA  {browser}")
        print(f"  GET curl        {curl}")
        if honest.startswith("HTTP 2"):
            print(f"  robots.txt      {http_get(host, UA_HONEST, '/robots.txt')}")
        verdict = classify(layers, honest, browser, curl)
        verdicts.append((label, host, verdict))
        print(f"  VERDICT: {verdict}\n")

    print("=" * 72)
    print("SUMMARY")
    for label, host, verdict in verdicts:
        print(f"  {label:38s} {verdict}")

    affected_v = [v for lbl, _, v in verdicts[:len(AFFECTED)] for v in [v]]
    controls_v = [v for lbl, _, v in verdicts[-len(CONTROLS):] for v in [v]]
    controls_ok = all(v.startswith("REACHABLE") for v in controls_v)
    print("\nINTERPRETATION")
    if not controls_ok:
        print("  Controls failed: the runner egress itself is impaired; "
              "affected-host verdicts above are not trustworthy this run.")
    elif len(set(affected_v)) == 1:
        print(f"  Controls clean and every affected host classifies the same "
              f"way -> ONE SYSTEMIC CAUSE: {affected_v[0]}")
    else:
        print("  Controls clean; affected hosts diverge -> per-host causes, "
              "read the verdicts individually.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
