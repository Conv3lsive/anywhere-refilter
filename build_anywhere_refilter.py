#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import re
import urllib.request
from pathlib import Path

DOMAINS_URL = "https://raw.githubusercontent.com/1andrevich/Re-filter-lists/main/domains_all.lst"
IPS_URL = "https://raw.githubusercontent.com/1andrevich/Re-filter-lists/main/ipsum.lst"
NOECH_URL = "https://github.com/Akiyamov/singbox-ech-list/releases/latest/download/domains_noech_dnsmasq.lst"
OUT = Path("dist")

DOMAIN_RE = re.compile(r"(?i)(?:^|[/=])([a-z0-9_\-](?:[a-z0-9_\-.]{0,251}[a-z0-9_\-])?\.[a-z0-9\-]{2,63})(?=$|[/#,:])")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "anywhere-refilter-builder/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def clean_domain(s: str) -> str | None:
    s = s.strip().lower().rstrip(".")
    if not s or s.startswith(("#", "//")):
        return None
    # re:filter occasionally contains literal IP-looking values in the domain list;
    # keep only DNS names here.
    try:
        ipaddress.ip_address(s)
        return None
    except ValueError:
        pass
    if "." not in s or " " in s or "/" in s:
        return None
    return s


def parse_plain_domains(text: str) -> set[str]:
    out: set[str] = set()
    for line in text.splitlines():
        d = clean_domain(line.split("#", 1)[0])
        if d:
            out.add(d)
    return out


def parse_dnsmasq_domains(text: str) -> set[str]:
    out: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "//")):
            continue
        # Accept a plain-domain line too.
        d = clean_domain(line)
        if d:
            out.add(d)
            continue
        # Typical dnsmasq/nftset forms contain the domain between /.../.
        for m in DOMAIN_RE.finditer(line):
            d = clean_domain(m.group(1))
            if d:
                out.add(d)
    return out


def parse_ips(text: str) -> tuple[set[str], set[str]]:
    v4, v6 = set(), set()
    for raw in text.splitlines():
        s = raw.split("#", 1)[0].strip()
        if not s:
            continue
        try:
            net = ipaddress.ip_network(s, strict=False)
        except ValueError:
            continue
        (v4 if net.version == 4 else v6).add(str(net))
    return v4, v6


def write_arrs(path: Path, name: str, rules: list[tuple[int, str]], routing: int | None = None) -> None:
    lines = [f"name = {name}"]
    if routing is not None:
        lines.append(f"routing = {routing}")
    lines.append("")
    lines += [f"{t}, {v}" for t, v in rules]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(exist_ok=True)

    all_domains = parse_plain_domains(fetch(DOMAINS_URL))
    noech_raw = parse_dnsmasq_domains(fetch(NOECH_URL))
    # Keep only domains that are still in the current Re:filter snapshot.
    noech = all_domains & noech_raw
    # Practical ECH set: current Re:filter minus Akiyamov's current noECH list.
    ech = all_domains - noech

    v4, v6 = parse_ips(fetch(IPS_URL))

    # Anywhere: 2 = domain suffix, 0 = IPv4 CIDR, 1 = IPv6 CIDR.
    write_arrs(
        OUT / "refilter-noech.arrs",
        "ReFilter noECH — PROXY",
        [(2, d) for d in sorted(noech)],
    )
    write_arrs(
        OUT / "refilter-ech.arrs",
        "ReFilter ECH — DIRECT",
        [(2, d) for d in sorted(ech)],
        routing=1,  # DIRECT can be seeded by .arrs
    )
    write_arrs(
        OUT / "refilter-ip.arrs",
        "ReFilter IP — PROXY",
        [(0, n) for n in sorted(v4)] + [(1, n) for n in sorted(v6)],
    )
    write_arrs(
        OUT / "force-proxy.arrs",
        "Force Proxy",
        [(2, "cloudflare-ech.com")],
    )

    # A robust non-ECH-split fallback as well.
    write_arrs(
        OUT / "refilter-all-domains.arrs",
        "ReFilter Domains — PROXY",
        [(2, d) for d in sorted(all_domains)],
    )

    print(f"domains total: {len(all_domains)}")
    print(f"noECH:         {len(noech)}")
    print(f"ECH/complement:{len(ech)}")
    print(f"IPv4 CIDRs:    {len(v4)}")
    print(f"IPv6 CIDRs:    {len(v6)}")


if __name__ == "__main__":
    main()
