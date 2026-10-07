# Anywhere + Re:filter

Generator for Anywhere `.arrs` routing subscriptions.

## Generated files

- `dist/refilter-noech.arrs` — assign **PROXY** in Anywhere.
- `dist/refilter-ech.arrs` — seeded as **DIRECT** on first import.
- `dist/refilter-ip.arrs` — assign **PROXY** in Anywhere.
- `dist/force-proxy.arrs` — assign **PROXY**; contains `cloudflare-ech.com`.
- `dist/refilter-all-domains.arrs` — simpler fallback: all Re:filter domains, assign **PROXY**.

## Recommended Anywhere routing

1. Select your VLESS configuration/chain as the default route.
2. Set mode to **Rule**.
3. Enable **Country Bypass: RU** if you want Russian destinations DIRECT.
4. Subscribe/import the rule sets.
5. Explicitly assign:
   - Force Proxy -> PROXY
   - ReFilter noECH -> PROXY
   - ReFilter ECH -> DIRECT
   - ReFilter IP -> PROXY
6. Keep `Force Proxy` above `ReFilter ECH` in the Routing list so an identical suffix tie is won by Force Proxy.

Unmatched traffic uses Anywhere's default route, so with your VLESS config selected it goes through VPN.

## Subscription URLs

After pushing this repo to GitHub, use Raw URLs ending in `.arrs`, e.g.:

`https://raw.githubusercontent.com/USER/REPO/main/dist/refilter-noech.arrs`

Anywhere only treats an HTTP(S) URL as a rule subscription when its path ends in `.arrs`.

## Notes on ECH split

Akiyamov publicly provides a current `noECH` dnsmasq list and binary ECH/noECH Sing-box rule sets. This generator intersects that `noECH` list with the current Re:filter domain list and treats the remainder as the ECH side. If you prefer maximum conservatism, skip the ECH split and use `refilter-all-domains.arrs -> PROXY` plus `refilter-ip.arrs -> PROXY`.
