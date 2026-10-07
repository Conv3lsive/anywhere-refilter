#!/usr/bin/env python3
"""Ordered Shadowrocket policy -> deterministic, validated Anywhere sets. Stdlib only."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import fnmatch
import hashlib
import ipaddress
from itertools import groupby
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
ACTIONS = {"PROXY", "DIRECT", "REJECT"}
MAX_RULES = 100_000
LABEL = re.compile(r"^[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?$")


class BuildError(ValueError):
    pass


class Audit:
    def __init__(self):
        self.counts = Counter()
        self.samples = defaultdict(list)

    def add(self, code, detail):
        self.counts[code] += 1
        if len(self.samples[code]) < 25:
            self.samples[code].append(detail)

    def as_dict(self):
        return {code: {"count": self.counts[code], "examples": self.samples[code]}
                for code in sorted(self.counts)}


@dataclass(frozen=True)
class Rule:
    kind: str
    value: str
    action: str
    group: str
    rank: int
    origin: str


def domain(value):
    value = value.strip().lower().rstrip(".")
    try:
        value = value.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise BuildError(f"Invalid IDN: {value}") from exc
    if not value or len(value) > 253 or not all(LABEL.fullmatch(s) for s in value.split(".")):
        raise BuildError(f"Invalid domain: {value!r}")
    return value


def parse_entry(line, audit, origin):
    """Return original matching kind and normalized value; unknown syntax is fatal."""
    fields = [s.strip() for s in line.split(",")]
    if len(fields) > 1:
        kind, value = fields[:2]
        kind = kind.upper()
        # Parent RULE-SET supplies the action, as in the original configuration.
        for modifier in fields[2:]:
            if modifier.upper() in ACTIONS:
                audit.add("upstream-action-overridden", {"source": origin, "action": modifier})
            elif modifier.lower() in {"no-resolve", "pre-matching"}:
                audit.add("modifier-not-expressible", {"source": origin, "modifier": modifier})
            else:
                raise BuildError(f"{origin}: unsupported modifier {modifier!r}")
        if kind == "DOMAIN":
            audit.add("exact-domain-to-suffix", {"source": origin, "domain": value})
            return "suffix", domain(value)
        if kind == "DOMAIN-SUFFIX":
            return "suffix", domain(value)
        if kind == "DOMAIN-KEYWORD":
            if not value or any(c in value for c in " \t\r\n,#"):
                raise BuildError(f"{origin}: invalid keyword")
            return "keyword", value.lower()
        if kind == "DOMAIN-WILDCARD":
            value = value.lower()
            if value.startswith("*.") and not any(c in value[2:] for c in "*?["):
                audit.add("wildcard-adds-apex", {"source": origin, "pattern": value})
                return "suffix", domain(value[2:])
            if not re.fullmatch(r"[a-z0-9_.*?-]+", value):
                raise BuildError(f"{origin}: unsupported wildcard {value!r}")
            # Only a single literal run has a documented safe approximation.
            tokens = [s for s in re.split(r"[*?]+", value) if s.strip(".")]
            if len(tokens) != 1:
                raise BuildError(f"{origin}: wildcard has multiple literal runs: {value}")
            audit.add("wildcard-to-keyword", {"source": origin, "pattern": value,
                                              "keyword": tokens[0].strip(".")})
            return "wildcard", value
        if kind in {"IP-CIDR", "IP-CIDR6", "IP6-CIDR"}:
            net = ipaddress.ip_network(value, strict=False)
            if (kind == "IP-CIDR" and net.version != 4) or (kind != "IP-CIDR" and net.version != 6):
                raise BuildError(f"{origin}: IP family mismatch")
            return "ip", str(net)
        raise BuildError(f"{origin}: unsupported rule type {kind!r}")
    value = fields[0]
    try:
        return "ip", str(ipaddress.ip_network(value, strict=False))
    except ValueError:
        if "/" in value or ":" in value:
            raise BuildError(f"{origin}: malformed IP/CIDR {value!r}")
    if value.startswith(("+.", "*.", ".")):
        prefix = "+." if value.startswith("+.") else "*." if value.startswith("*.") else "."
        if prefix == "+.":
            audit.add("domain-set-plus-prefix", {"source": origin, "value": value})
        if prefix in {"*.", "."}:
            audit.add("wildcard-adds-apex", {"source": origin, "pattern": value})
        return "suffix", domain(value[len(prefix):])
    audit.add("plain-domain-to-suffix", {"source": origin, "domain": value})
    return "suffix", domain(value)


def useful_lines(text):
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith(("//", ";")):
            yield number, line


def parse_conf(text):
    general, hosts, rows = {}, {}, []
    section = ""
    for number, line in useful_lines(text):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].lower()
        elif section in {"general", "host"}:
            if "=" not in line:
                raise BuildError(f"Source line {number}: expected key = value")
            key, value = (s.strip() for s in line.split("=", 1))
            (general if section == "general" else hosts)[key.lower()] = value
        elif section == "rule":
            fields = [s.strip() for s in line.split(",")]
            kind = fields[0].upper()
            if kind == "FINAL":
                if len(fields) != 2 or fields[1].upper() != "PROXY":
                    raise BuildError("This migration requires FINAL,PROXY")
            elif len(fields) < 3 or fields[2].upper() not in ACTIONS:
                raise BuildError(f"Source line {number}: invalid rule/action")
            if any(row[1][0].upper() == "FINAL" for row in rows):
                raise BuildError("Rules after FINAL are unreachable; remove them explicitly")
            rows.append((number, fields))
        elif section:
            raise BuildError(f"Unsupported source section [{section}] at line {number}")
    if not rows or rows[-1][1] != ["FINAL", "PROXY"]:
        raise BuildError("Source must end its [Rule] section with FINAL,PROXY")
    return general, hosts, rows


def discover_urls(rows, config):
    urls = set()
    for number, fields in rows:
        kind = fields[0].upper()
        if kind in {"DOMAIN-SET", "RULE-SET"}:
            urls.add(fields[1])
        elif kind == "GEOIP":
            try:
                urls.add(config["geoip"][fields[1].upper()])
            except KeyError as exc:
                raise BuildError(f"No GeoIP source for {fields[1]} (line {number})") from exc
    if config["refilter"]["enabled"]:
        urls.update(config["refilter"][key] for key in ("domains", "ips"))
    return sorted(urls)


def fetch_sources(urls, cache, offline=False):
    cache.mkdir(parents=True, exist_ok=True)

    def fetch(url):
        if not url.startswith("https://"):
            raise BuildError(f"Only HTTPS upstreams are supported: {url}")
        path = cache / (hashlib.sha256(url.encode()).hexdigest() + ".txt")
        if offline:
            data = path.read_bytes()
        else:
            for attempt in range(3):
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "anywhere-shadowrocket/1.0"})
                    with urllib.request.urlopen(request, timeout=45) as response:
                        if not response.geturl().startswith("https://"):
                            raise BuildError(f"Insecure redirect: {url}")
                        data = response.read(20_000_001)
                    break
                except (OSError, TimeoutError):
                    if attempt == 2:
                        raise
                    time.sleep(attempt + 1)
            if not data or len(data) > 20_000_000:
                raise BuildError(f"Empty or oversized source: {url}")
            path.write_bytes(data)
        text = data.decode("utf-8-sig")
        if text.lstrip().lower().startswith(("<!doctype", "<html")):
            raise BuildError(f"HTML instead of rules: {url}")
        return url, (text, {"url": url, "sha256": hashlib.sha256(data).hexdigest(),
                            "bytes": len(data), "lines": len(text.splitlines())})

    with ThreadPoolExecutor(max_workers=6) as pool:
        fetched = dict(pool.map(fetch, urls))
    return {url: value[0] for url, value in fetched.items()}, [fetched[url][1] for url in urls]


def expand_rules(general, rows, config, fetched, audit):
    rules = []

    def add(kind, value, action, group, origin):
        rules.append(Rule(kind, value, action, group, len(rules), origin))

    # These are transport exclusions in Shadowrocket. DIRECT is their closest
    # routing equivalent; they still pass through Anywhere's tunnel engine.
    for setting in ("skip-proxy", "tun-excluded-routes"):
        for value in filter(None, (s.strip() for s in general.get(setting, "").split(","))):
            origin = f"General.{setting}"
            kind, normalized = parse_entry(value, audit, origin)
            add(kind, normalized, "DIRECT", "00-local-direct", origin)
    audit.add("tunnel-exclusions-to-direct", {"settings": ["skip-proxy", "tun-excluded-routes"]})

    for number, fields in rows:
        kind, value = fields[:2]
        kind = kind.upper()
        origin = f"Ru-Direct.conf:{number}"
        if kind == "FINAL":
            continue
        action = fields[2].upper()
        for modifier in fields[3:]:
            if modifier.lower() not in {"no-resolve", "pre-matching"}:
                raise BuildError(f"{origin}: unsupported modifier {modifier!r}")
            audit.add("modifier-not-expressible", {"source": origin, "modifier": modifier})
        if kind in {"DOMAIN-SET", "RULE-SET", "GEOIP"}:
            if kind == "GEOIP":
                country = value.upper()
                url = config["geoip"][country]
                group = f"20-geo-{country.lower()}-{action.lower()}"
                audit.add("geoip-database-difference", {"country": country, "url": url})
            else:
                url = value
                if "community.antifilter.download" in url:
                    group = f"10-antifilter-{action.lower()}"
                elif url.endswith("domain_ips.list"):
                    group = f"40-domain-ips-{action.lower()}"
                elif url.endswith("domains_geo_detect.list"):
                    group = f"50-geo-detect-{action.lower()}"
                elif url.endswith("reject.list"):
                    group = f"60-reject-{action.lower()}"
                else:
                    group = f"source-{number:04d}-{action.lower()}"
            before = len(rules)
            for upstream_line, text in useful_lines(fetched[url]):
                entry_origin = f"{url}:{upstream_line}"
                entry_kind, entry_value = parse_entry(text, audit, entry_origin)
                if kind == "GEOIP" and entry_kind != "ip":
                    raise BuildError(f"{entry_origin}: non-IP in GeoIP file")
                add(entry_kind, entry_value, action, group, entry_origin)
            if len(rules) == before:
                raise BuildError(f"No rules parsed from {url}")
        else:
            group = "05-prematch-" + action.lower() if "pre-matching" in fields[3:] else "30-explicit-" + action.lower()
            entry_kind, entry_value = parse_entry(",".join(fields[:2]), audit, origin)
            add(entry_kind, entry_value, action, group, origin)
    return rules


def wildcard_keyword(pattern):
    return re.split(r"[*?]+", pattern)[1].strip(".") if pattern.startswith(("*", "?")) else re.split(r"[*?]+", pattern)[0].strip(".")


def compile_domains(rules, audit):
    """Materialize first-match decisions at every known suffix boundary.

    Infinite keyword/wildcard intersections with suffixes cannot be encoded;
    README describes that remaining limitation explicitly.
    """
    suffixes = {}
    predicates = []
    for rule in rules:
        if rule.kind == "suffix":
            suffixes.setdefault(rule.value, rule)
        elif rule.kind in {"keyword", "wildcard"}:
            predicates.append(rule)
    result = defaultdict(set)
    for value, original in sorted(suffixes.items()):
        labels = value.split(".")
        candidates = [suffixes[ancestor] for i in range(len(labels))
                      if (ancestor := ".".join(labels[i:])) in suffixes]
        candidates.extend(rule for rule in predicates
                          if (rule.kind == "keyword" and rule.value in value)
                          or (rule.kind == "wildcard" and fnmatch.fnmatchcase(value, rule.value)))
        winner = min(candidates, key=lambda r: r.rank)
        result[(winner.group, winner.action)].add((2, value))
        if winner.action != original.action:
            audit.add("suffix-precedence-reassigned", {"suffix": value, "from": original.action,
                      "to": winner.action, "winner": winner.origin, "original": original.origin})
    keywords = {}
    for rule in predicates:
        value = rule.value if rule.kind == "keyword" else wildcard_keyword(rule.value)
        keywords.setdefault(value, rule)
    for value, original in keywords.items():
        # A prior keyword contained in a longer keyword always matches first.
        candidates = [rule for token, rule in keywords.items() if token in value]
        winner = min(candidates, key=lambda r: r.rank)
        result[(winner.group, winner.action)].add((3, value))
        if winner.action != original.action:
            audit.add("keyword-precedence-reassigned", {"keyword": value, "to": winner.action})
    if keywords and suffixes:
        audit.add("keyword-suffix-runtime-intersection", {
            "example": "tiktok.bank.ru matches DIRECT suffix ru before PROXY keyword tiktok in Anywhere",
            "explanation": "Known suffix roots are compensated; arbitrary future subdomains cannot be enumerated."})
    return result


def merge_intervals(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def subtract_intervals(intervals, claimed):
    """Linear difference of sorted disjoint intervals, without enumerating IPs."""
    result, j = [], 0
    for start, end in intervals:
        while j < len(claimed) and claimed[j][1] < start:
            j += 1
        k, cursor = j, start
        while k < len(claimed) and claimed[k][0] <= end:
            a, b = claimed[k]
            if cursor < a:
                result.append((cursor, min(end, a - 1)))
            cursor = max(cursor, b + 1)
            if cursor > end:
                break
            k += 1
        if cursor <= end:
            result.append((cursor, end))
    return result


def compile_ips(rules, audit):
    result = defaultdict(set)
    claimed = {4: [], 6: []}
    ip_rules = [r for r in rules if r.kind == "ip"]
    for key, batch in groupby(ip_rules, key=lambda r: (r.group, r.action)):
        intervals = {4: [], 6: []}
        for rule in batch:
            net = ipaddress.ip_network(rule.value)
            intervals[net.version].append((int(net.network_address), int(net.broadcast_address)))
        for version in (4, 6):
            original = merge_intervals(intervals[version])
            remaining = subtract_intervals(original, claimed[version])
            if original != remaining:
                audit.add("ip-precedence-subtracted", {"group": key[0], "action": key[1], "family": version,
                          "addresses_removed": sum(b-a+1 for a,b in original) - sum(b-a+1 for a,b in remaining)})
            address_cls = ipaddress.IPv4Address if version == 4 else ipaddress.IPv6Address
            for start, end in remaining:
                for net in ipaddress.summarize_address_range(address_cls(start), address_cls(end)):
                    result[key].add((0 if version == 4 else 1, str(net)))
            claimed[version] = merge_intervals(claimed[version] + original)
    return result


def compile_policy(rules, audit):
    result = compile_domains(rules, audit)
    for key, entries in compile_ips(rules, audit).items():
        result[key].update(entries)
    return result


def refilter_sets(config, fetched, audit):
    if not config["refilter"]["enabled"]:
        return {}
    output = {}
    for category, label in (("domains", "refilter-domains"), ("ips", "refilter-ip")):
        url = config["refilter"][category]
        entries = set()
        for number, line in useful_lines(fetched[url]):
            kind, value = parse_entry(line, audit, f"{url}:{number}")
            if category == "domains" and kind == "ip":
                audit.add("refilter-domain-literal-ip-omitted", {"value": value})
                continue
            if category == "ips" and kind != "ip":
                raise BuildError(f"{url}:{number}: expected IP")
            entries.add((2, value) if kind == "suffix" else
                        (0 if ipaddress.ip_network(value).version == 4 else 1, value))
        if not entries:
            raise BuildError(f"No optional Re:filter rules from {url}")
        output[(label, "PROXY")] = entries
    return output


def sort_rule(entry):
    kind, value = entry
    if kind < 2:
        net = ipaddress.ip_network(value)
        return kind, int(net.network_address), net.prefixlen
    return kind, value


def write_set(stage, prefix, name, action, entries, cap, catalog, layout):
    entries = sorted(set(entries), key=sort_rule)
    # An empty policy is a valid set and can clear a previous subscription.
    chunks = [entries[i:i+cap] for i in range(0, len(entries), cap)] or [[]]
    for index, chunk in enumerate(chunks, 1):
        relative = f"{prefix}-{index:03d}.arrs"
        path = stage / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"name = {name} {index:03d} - {action}"]
        if action in {"DIRECT", "REJECT"}:
            lines.append(f"routing = {1 if action == 'DIRECT' else 2}")
        lines += ["# Generated by build_rules.py; do not edit.",
                  f"# Assign this set explicitly to {action} in Anywhere.", ""]
        lines += [f"{kind}, {value}" for kind, value in chunk]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        catalog.append({"path": relative, "action": action, "rules": len(chunk), "layout": layout,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})


def validate(stage):
    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("managed_by") != "anywhere-shadowrocket":
        raise BuildError("Not an Anywhere Shadowrocket output directory")
    seen = defaultdict(dict)
    listed = set()
    for item in manifest["files"]:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise BuildError("Unsafe path in manifest")
        path = stage / relative
        listed.add(item["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise BuildError(f"Hash mismatch: {relative}")
        entries = []
        for number, line in useful_lines(path.read_text(encoding="utf-8")):
            if "=" in line:
                continue
            kind, value = (s.strip() for s in line.split(",", 1))
            if kind not in {"0", "1", "2", "3"} or not value:
                raise BuildError(f"Invalid .arrs entry: {relative}:{number}")
            kind = int(kind)
            if kind < 2:
                net = ipaddress.ip_network(value, strict=True)
                if net.version != (4 if kind == 0 else 6):
                    raise BuildError(f"Incorrect IP family: {relative}:{number}")
            elif kind == 2 and domain(value) != value:
                raise BuildError(f"Unnormalized domain: {relative}:{number}")
            entry = kind, value
            prior = seen[item["layout"]].get(entry)
            if prior and prior != item["action"]:
                raise BuildError(f"Conflicting actions for {entry}")
            seen[item["layout"]][entry] = item["action"]
            entries.append(entry)
        if len(entries) != item["rules"] or len(entries) > MAX_RULES or len(set(entries)) != len(entries):
            raise BuildError(f"Bad rule count/duplicates: {relative}")
    if {p.relative_to(stage).as_posix() for p in stage.rglob("*.arrs")} != listed:
        raise BuildError("Unlisted .arrs files")
    # Aggregate and source layouts must contain exactly the same action policies.
    if seen["actions"] != seen["sets"]:
        raise BuildError("Actions and source sets differ")
    return manifest


def explain(output, host=None, address=None):
    manifest = validate(output)
    rules = []
    for item in manifest["files"]:
        if item["layout"] != "actions":
            continue
        for _, line in useful_lines((output / item["path"]).read_text(encoding="utf-8")):
            if "=" not in line:
                kind, value = (s.strip() for s in line.split(",", 1))
                rules.append((int(kind), value, item["action"], item["path"]))
    matches = []
    if host is not None:
        host = domain(host)
        suffixes = [r for r in rules if r[0] == 2 and (host == r[1] or host.endswith("."+r[1]))]
        matches = sorted(suffixes, key=lambda r: len(r[1].split(".")), reverse=True)
        if not matches:
            matches = sorted((r for r in rules if r[0] == 3 and r[1] in host),
                             key=lambda r: len(r[1]), reverse=True)
    if address is not None:
        ip = ipaddress.ip_address(address)
        matches = sorted((r for r in rules if r[0] == (0 if ip.version == 4 else 1)
                          and ip in ipaddress.ip_network(r[1])),
                         key=lambda r: ipaddress.ip_network(r[1]).prefixlen, reverse=True)
    print(json.dumps({"destination": host or address, "action": matches[0][2] if matches else "PROXY",
                      "matched_rule": matches[0] if matches else None,
                      "scope": "Generated User-tier rules only; no live DNS or built-in rules simulated."},
                     ensure_ascii=False, indent=2))


def build(source, config_path, output, cache, offline=False, without_refilter=False):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if without_refilter:
        config["refilter"]["enabled"] = False
    cap = config["rules_per_file"]
    if isinstance(cap, bool) or not isinstance(cap, int) or not 1 <= cap <= MAX_RULES:
        raise BuildError(f"rules_per_file must be 1..{MAX_RULES}")
    source_data = source.read_bytes()
    general, hosts, rows = parse_conf(source_data.decode("utf-8-sig"))
    audit = Audit()
    fetched, lock = fetch_sources(discover_urls(rows, config), cache, offline)
    rules = expand_rules(general, rows, config, fetched, audit)
    compiled = compile_policy(rules, audit)
    optional = refilter_sets(config, fetched, audit)
    old_manifest = None
    if output.exists():
        if not (output / "manifest.json").is_file():
            raise BuildError(f"Refusing to replace unmanaged directory {output}")
        old_manifest = validate(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".anywhere-build-", dir=output.parent))
    backup = None
    try:
        catalog = []
        aggregates = {action: set() for action in ACTIONS}
        for (group, action), entries in sorted(compiled.items()):
            aggregates[action].update(entries)
            write_set(stage, "sets/"+group, group, action, entries, cap, catalog, "sets")
        for action in sorted(ACTIONS):
            write_set(stage, "actions/"+action.lower(), "Ru-Direct "+action, action,
                      aggregates[action], cap, catalog, "actions")
        for (group, action), entries in sorted(optional.items()):
            write_set(stage, "optional/"+group, "Optional "+group, action, entries, cap, catalog, "optional")
        # Leave empty tombstones for removed shards, so old subscriptions clear
        # their previous content on refresh instead of retaining stale rules.
        current = {item["path"] for item in catalog}
        if old_manifest:
            for item in old_manifest["files"]:
                if item["path"] not in current:
                    path = stage / item["path"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("name = Retired " + path.stem + "\n# Empty retired subscription.\n", encoding="utf-8")
                    catalog.append({**item, "rules": 0, "retired": True,
                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        manifest = {"schema": 1, "managed_by": "anywhere-shadowrocket", "default_action": "PROXY",
                    "rules_per_file": cap, "files": sorted(catalog, key=lambda i: i["path"])}
        report = {"source": "source/Ru-Direct.conf", "source_sha256": hashlib.sha256(source_data).hexdigest(),
                  "input_rules_expanded": len(rules), "general": general, "hosts": hosts,
                  "action_rule_counts": {a: len(aggregates[a]) for a in sorted(ACTIONS)},
                  "limitations": audit.as_dict()}
        for name, value in (("manifest.json", manifest), ("report.json", report),
                            ("sources.lock.json", {"source_sha256": report["source_sha256"], "upstreams": lock})):
            (stage / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+"\n", encoding="utf-8")
        lines = ["# Generated subscription catalog", "", "Choose **actions** OR **sets**. Optional Re:filter changes the original policy.", "",
                 "| Layout | File | Action | Rules |", "|---|---|---|---:|"]
        for item in manifest["files"]:
            if not item.get("retired"):
                lines.append(f"| {item['layout']} | [{item['path']}]({item['path']}) | {item['action']} | {item['rules']} |")
        (stage / "SUBSCRIPTIONS.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
        validate(stage)
        if output.exists():
            backup = Path(tempfile.mkdtemp(prefix=".anywhere-old-", dir=output.parent))
            backup.rmdir()
            os.replace(output, backup)
        try:
            os.replace(stage, output)
        except BaseException:
            if backup:
                os.replace(backup, output)
                backup = None
            raise
        if backup:
            shutil.rmtree(backup)
        return manifest, report
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "source/Ru-Direct.conf")
    parser.add_argument("--config", type=Path, default=ROOT / "sources.json")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".cache/upstream")
    parser.add_argument("--offline", action="store_true", help="Use explicitly cached snapshots; never enabled in CI")
    parser.add_argument("--without-refilter", action="store_true", help="Skip optional Re:filter downloads")
    parser.add_argument("--check", action="store_true", help="Validate existing dist without downloading")
    dest = parser.add_mutually_exclusive_group()
    dest.add_argument("--explain-host")
    dest.add_argument("--explain-ip")
    args = parser.parse_args()
    try:
        if args.explain_host or args.explain_ip:
            explain(args.output, args.explain_host, args.explain_ip)
        elif args.check:
            result = validate(args.output)
            print(f"Validated {len(result['files'])} .arrs files")
        else:
            manifest, report = build(args.source, args.config, args.output, args.cache_dir,
                                     args.offline, args.without_refilter)
            print(json.dumps({"files": len(manifest["files"]), "rules": report["action_rule_counts"],
                              "source_sha256": report["source_sha256"]}, indent=2))
    except (OSError, ValueError, KeyError, UnicodeError) as exc:
        print(f"Build failed; previous dist preserved: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
