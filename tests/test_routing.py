"""Regression tests for policy outcomes and safe publication, without network."""
import ipaddress
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_rules as b


def rules(*rows):
    return [b.Rule(kind, value, action, group, i, f"fixture:{i}")
            for i, (kind, value, action, group) in enumerate(rows)]


def evaluate(policy, host=None, address=None):
    entries = [(kind, value, action) for (_, action), values in policy.items() for kind, value in values]
    if host:
        suffixes = [r for r in entries if r[0] == 2 and (host == r[1] or host.endswith("."+r[1]))]
        if suffixes:
            return max(suffixes, key=lambda r: len(r[1].split(".")))[2]
        keywords = [r for r in entries if r[0] == 3 and r[1] in host]
        if keywords:
            return max(keywords, key=lambda r: len(r[1]))[2]
    if address:
        ip = ipaddress.ip_address(address)
        matched = [r for r in entries if r[0] == (0 if ip.version == 4 else 1)
                   and ip in ipaddress.ip_network(r[1])]
        if matched:
            return max(matched, key=lambda r: ipaddress.ip_network(r[1]).prefixlen)[2]
    return "PROXY"


class PolicyTests(unittest.TestCase):
    def test_late_reject_under_ru_stays_direct(self):
        policy = b.compile_policy(rules(
            ("suffix", "ru", "DIRECT", "manual"),
            ("suffix", "ad.mail.ru", "REJECT", "reject")), b.Audit())
        self.assertEqual(evaluate(policy, host="ad.mail.ru"), "DIRECT")
        self.assertEqual(evaluate(policy, host="sub.ad.mail.ru"), "DIRECT")

    def test_antifilter_before_ru_preserves_proxy_exception(self):
        policy = b.compile_policy(rules(
            ("suffix", "blocked.ru", "PROXY", "antifilter"),
            ("suffix", "ru", "DIRECT", "manual"),
            ("suffix", "ads.blocked.ru", "REJECT", "reject")), b.Audit())
        self.assertEqual(evaluate(policy, host="ads.blocked.ru"), "PROXY")
        self.assertEqual(evaluate(policy, host="bank.ru"), "DIRECT")

    def test_keywords_materialized_on_known_suffix_roots(self):
        policy = b.compile_policy(rules(
            ("keyword", "tiktok", "PROXY", "prematch"),
            ("keyword", "yandex", "DIRECT", "manual"),
            ("suffix", "api.tiktok.example", "DIRECT", "late"),
            ("suffix", "ads.yandex.com", "REJECT", "reject")), b.Audit())
        self.assertEqual(evaluate(policy, host="api.tiktok.example"), "PROXY")
        self.assertEqual(evaluate(policy, host="ads.yandex.com"), "DIRECT")

    def test_runtime_keyword_suffix_limit_is_reported(self):
        audit = b.Audit()
        policy = b.compile_policy(rules(
            ("keyword", "tiktok", "PROXY", "prematch"),
            ("suffix", "ru", "DIRECT", "manual")), audit)
        self.assertEqual(evaluate(policy, host="tiktok.bank.ru"), "DIRECT")
        self.assertIn("keyword-suffix-runtime-intersection", audit.counts)

    def test_prior_keyword_wins_over_longer_late_keyword(self):
        policy = b.compile_policy(rules(
            ("keyword", "short", "DIRECT", "first"),
            ("keyword", "longshort", "REJECT", "late")), b.Audit())
        self.assertEqual(evaluate(policy, host="longshort.example"), "DIRECT")

    def test_early_lan_and_geo_override_proxy_host_ips(self):
        policy = b.compile_policy(rules(
            ("ip", "127.0.0.0/8", "DIRECT", "local"),
            ("ip", "5.0.0.0/8", "DIRECT", "ru"),
            ("ip", "127.0.0.1/32", "PROXY", "external"),
            ("ip", "5.61.59.57/32", "PROXY", "external"),
            ("ip", "8.8.8.8/32", "PROXY", "external")), b.Audit())
        self.assertEqual(evaluate(policy, address="127.0.0.1"), "DIRECT")
        self.assertEqual(evaluate(policy, address="5.61.59.57"), "DIRECT")
        self.assertEqual(evaluate(policy, address="8.8.8.8"), "PROXY")

    def test_ipv4_and_ipv6_partial_overlap_is_partitioned(self):
        policy = b.compile_policy(rules(
            ("ip", "192.0.2.0/25", "DIRECT", "first"),
            ("ip", "2001:db8::/33", "DIRECT", "first"),
            ("ip", "192.0.2.0/24", "REJECT", "late"),
            ("ip", "2001:db8::/32", "REJECT", "late")), b.Audit())
        self.assertEqual(evaluate(policy, address="192.0.2.1"), "DIRECT")
        self.assertEqual(evaluate(policy, address="192.0.2.200"), "REJECT")
        self.assertEqual(evaluate(policy, address="2001:db8::1"), "DIRECT")
        self.assertEqual(evaluate(policy, address="2001:db8:8000::1"), "REJECT")

    def test_wildcard_approximation_and_idn(self):
        audit = b.Audit()
        self.assertEqual(b.parse_entry("DOMAIN-SUFFIX,рф", audit, "test"), ("suffix", "xn--p1ai"))
        self.assertEqual(b.parse_entry("+.ad.example", audit, "test"), ("suffix", "ad.example"))
        self.assertEqual(b.parse_entry("203.0.113.7", audit, "test"), ("ip", "203.0.113.7/32"))
        self.assertEqual(b.parse_entry("2001:db8::1", audit, "test"), ("ip", "2001:db8::1/128"))
        kind, pattern = b.parse_entry("DOMAIN-WILDCARD,*.vk*", audit, "test")
        self.assertEqual((kind, b.wildcard_keyword(pattern)), ("wildcard", "vk"))
        self.assertIn("wildcard-to-keyword", audit.counts)

    def test_unknown_upstream_rules_are_fatal(self):
        for value in ("DST-PORT,443", "DOMAIN-REGEX,.*test.*", "DOMAIN-WILDCARD,a*b*c"):
            with self.assertRaises(b.BuildError):
                b.parse_entry(value, b.Audit(), "test")


class PublicationTests(unittest.TestCase):
    def test_determinism_shards_retirement_and_failure_preserves_dist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, config, output = root/"source.conf", root/"sources.json", root/"dist"
            source.write_text("[General]\n[Rule]\nDOMAIN-SET,https://test.example/domains,PROXY\nFINAL,PROXY\n", encoding="utf-8")
            config.write_text(json.dumps({"geoip": {}, "refilter": {"enabled": False}, "rules_per_file": 2}))
            upstream = "a.example\nb.example\nc.example\nd.example\ne.example\n"
            def fetched(text):
                return ({"https://test.example/domains": text}, [{"url": "fixture", "sha256": "fixture"}])
            with patch.object(b, "fetch_sources", return_value=fetched(upstream)):
                b.build(source, config, output, root/"cache")
                before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
                b.build(source, config, output, root/"cache")
                self.assertEqual(before, {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()})
            manifest = b.validate(output)
            self.assertEqual(len([i for i in manifest["files"] if i["path"].startswith("actions/proxy")]), 3)
            with patch.object(b, "fetch_sources", return_value=fetched("a.example\n")):
                b.build(source, config, output, root/"cache")
            manifest = b.validate(output)
            retired = [i for i in manifest["files"] if i.get("retired")]
            self.assertEqual(len(retired), 4)
            self.assertTrue(all(i["rules"] == 0 for i in retired))
            before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            with patch.object(b, "fetch_sources", return_value=fetched("DST-PORT,443\n")):
                with self.assertRaises(b.BuildError):
                    b.build(source, config, output, root/"cache")
            self.assertEqual(before, {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
