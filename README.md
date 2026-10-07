# Anywhere + Re:filter

Auto-updating routing subscriptions for Anywhere.

## Quick import

**[Add all 4 ECH / noECH sets to Anywhere](https://conv3lsive.github.io/anywhere-refilter/?preset=ech&open=1)**

Open the link on a device with Anywhere installed and confirm the import.
If the app does not open, tap **Add to Anywhere** on the import page.

| Rule set | Route | Assignment |
|---|---|---|
| Force Proxy | **PROXY** | Select in Routing |
| ReFilter noECH | **PROXY** | Select in Routing |
| ReFilter ECH | **DIRECT** | Automatic on first import |
| ReFilter IP | **PROXY** | Select in Routing |

### Setup

1. Select your **VLESS / chain** as the default route and enable **Rule** mode.
2. Assign **PROXY** to Force Proxy, ReFilter noECH and ReFilter IP.
3. Place **Force Proxy above ReFilter ECH** in Routing.
4. Enable **Country Bypass → RU** for Russian destinations.
5. Turn **Prevent DNS Leak off** to apply IP rules to resolved IPv4 addresses
   when no domain rule matches.

ECH receives **DIRECT** automatically. Anywhere requires **PROXY** to be selected
in the app; leaving a set on Default gives it a different priority.
The import link does not select your proxy, Rule mode or Country Bypass.

### Without ECH splitting

**[Add the 3-set all-domains preset](https://conv3lsive.github.io/anywhere-refilter/?preset=all&open=1)**

Imports Force Proxy, ReFilter Domains and ReFilter IP. Assign **PROXY** to all
three and use the same setup above. Choose one preset.

## Individual sets

| Rule set | Route | Import | Subscription URL |
|---|---|---|---|
| Force Proxy | **PROXY** | [Add](https://conv3lsive.github.io/anywhere-refilter/?set=force-proxy&open=1) | [Raw URL](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/force-proxy.arrs) |
| ReFilter noECH | **PROXY** | [Add](https://conv3lsive.github.io/anywhere-refilter/?set=refilter-noech&open=1) | [Raw URL](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/refilter-noech.arrs) |
| ReFilter ECH | **DIRECT** | [Add](https://conv3lsive.github.io/anywhere-refilter/?set=refilter-ech&open=1) | [Raw URL](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/refilter-ech.arrs) |
| ReFilter IP | **PROXY** | [Add](https://conv3lsive.github.io/anywhere-refilter/?set=refilter-ip&open=1) | [Raw URL](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/refilter-ip.arrs) |
| ReFilter Domains | **PROXY** | [Add](https://conv3lsive.github.io/anywhere-refilter/?set=refilter-all-domains&open=1) | [Raw URL](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/refilter-all-domains.arrs) |

For manual import, copy a subscription link into Anywhere's Routing URL field.
The [import page](https://conv3lsive.github.io/anywhere-refilter/) also provides
**Copy URL** buttons. Use Safari if your browser blocks opening Anywhere.

## Updates

[GitHub Actions](https://github.com/Conv3lsive/anywhere-refilter/actions/workflows/update.yml)
rebuilds the lists daily at **03:17 UTC** and commits changes automatically.
To run it immediately: **Actions → Update Anywhere ReFilter rules → Run workflow**.
Refresh subscriptions in Anywhere to receive the latest rules.

## Sources

- [Re:filter](https://github.com/1andrevich/Re-filter-lists): domains and IPs.
- [Akiyamov](https://github.com/Akiyamov/singbox-ech-list): noECH domain list.
- [Anywhere routing format](https://github.com/NodePassProject/Anywhere/blob/main/Documentations/Routing.md)
  and [batch import](https://github.com/NodePassProject/Anywhere#import-rule-sets).

The ECH set is estimated as Re:filter minus the noECH list; membership alone
does not verify ECH support. The all-domains preset routes all Re:filter domains
through the proxy.

Local build: `python3 build_anywhere_refilter.py`.
