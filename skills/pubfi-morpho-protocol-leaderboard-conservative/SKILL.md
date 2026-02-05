---
name: morpho-protocol-leaderboard-conservative
description: Use when you need a conservative Morpho Vaults leaderboard (Ethereum/Base/Arbitrum) with exposure-asset allowlist enforcement, filtered by liquidity >$10M and ranked by net APY.
argument-hint: [optional: chain, optional: limit]
status: draft
---

# Morpho Protocol Leaderboard (Conservative)

> **Conservative DeFi Vaults Ranking**

## Overview

Uses Morpho Vaults V1 (legacy) GraphQL data to fetch vaults on Ethereum, Base, and Arbitrum, enforce strict exposure-asset allowlists, apply conservative safety and liquidity filters, and rank by Net APY. No mock data is allowed.

## Rules

**Deposit Assets (Canonical):**
- USDC, USDT, ETH, BTC

**Exposure Assets (Enforced):**
- BTC, ETH, WETH, WBTC, cbBTC, cbETH, wstETH, USDS, sUSDS, USDT, USDC

**Safety:**
- `whitelisted` must be true
- `warnings` must be empty

**Thresholds:**
- Minimum Liquidity: $10,000,000 USD (use `state.totalAssetsUsd`, fallback to `state.totalAssets / 10^asset.decimals` for USDC/USDT)
- Net APY: `state.netApy` > 0

**Target Chains:**
- Ethereum (Chain ID: 1)
- Base (Chain ID: 8453)
- Arbitrum (Chain ID: 42161)

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| chain | string | all | Target chain: ethereum, base, arbitrum, or all |
| limit | number | 10 | Number of vaults to return (1-100) |

## Execution Workflow

### Step 1: Initialize
```yaml
1. Map chain param to chain IDs:
   - ethereum -> [1]
   - base -> [8453]
   - arbitrum -> [42161]
   - all -> [1, 8453, 42161]
2. Set result limit (default: 10, max: 100)
3. If chain == all, plan to query each chain separately and merge results
4. Enable pagination with `skip` and `first` (default: `first=200`, `skip=0`) and loop until a page returns `< first` items; optional `max_pages` safety cap
5. Define canonical deposit assets: USDC, USDT, ETH, BTC
6. Define conservative safety gate: whitelisted == true AND warnings.length == 0
```

### Step 2: Fetch Data (Vaults V1 - Legacy)
```yaml
Source: Morpho GraphQL API
Endpoint: https://api.morpho.org/graphql
```

**GraphQL query (V1):**
```graphql
query VaultsConservative($chainIds: [Int!], $first: Int!, $skip: Int!) {
  vaults(first: $first, skip: $skip, where: { chainId_in: $chainIds }, orderBy: TotalAssetsUsd) {
    items {
      address
      symbol
      name
      whitelisted
      warnings { type level }
      chain { id network }
      asset { symbol address decimals }
      state {
        netApy
        totalAssets
        totalAssetsUsd
        allocation {
          market {
            loanAsset { symbol address }
            collateralAsset { symbol address }
          }
        }
      }
    }
  }
}
```

**Example variables:**
```json
{ "chainIds": [1, 8453, 42161], "first": 200, "skip": 0 }
```

**If `chain=all`, run the query once per chain to avoid timeouts, then merge results.**

**If a chain returns exactly `first` items, paginate with `skip` (e.g., `skip=200`) or increase `first` for that chain.**

### Step 3: Normalize and Filter
```yaml
Normalization:
  - depositAsset := asset.symbol (uppercase), fallback to infer from vault symbol/name:
      * if contains USDC -> USDC
      * else if contains USDT -> USDT
      * else if contains WBTC or CBBTC or BTC -> BTC
      * else if contains WSTETH or CBETH or WETH or ETH -> ETH
      * else -> UNKNOWN (exclude)
  - exposureAssets := unique set of allocation.market.loanAsset.symbol + allocation.market.collateralAsset.symbol (uppercase)
  - if any allocation market is missing a symbol, exclude (unknown exposure)
  - if exposureAssets is empty, exclude
  - liquidityUsd := state.totalAssetsUsd
  - if liquidityUsd is null AND depositAsset in [USDC, USDT]:
      liquidityUsd := state.totalAssets / (10 ^ asset.decimals)
  - if liquidityUsd is still null, exclude (cannot verify $10M threshold)
  - netApyPct := state.netApy * 100

Filtering:
  - whitelisted == true
  - warnings.length == 0
  - liquidityUsd >= 10_000_000
  - state.netApy > 0
  - depositAsset in [USDC, USDT, ETH, BTC]
  - exposureAssets ⊆ [BTC, ETH, WETH, WBTC, cbBTC, cbETH, wstETH, USDS, sUSDS, USDT, USDC]
```

### Step 4: Sort and Rank
```yaml
Sorting:
  - Primary: state.netApy (descending)
  - Secondary: liquidityUsd (descending)

Take:
  - Top N = limit
```

### Step 5: Build Vault Link
```yaml
link := https://app.morpho.org/{network}/vault/{address}
# network comes from chain.network; lowercase it for URL safety
```

### Step 6: Reference Script (Python)
```bash
# Optional: run end-to-end without guessing
# CHAIN=all LIMIT=10 FIRST=200 SKIP=0 MAX_PAGES=0   # MAX_PAGES=0 means no cap
python - <<'PY'
import json, os, sys, urllib.request
from datetime import datetime, timezone

QUERY = """
query VaultsConservative($chainIds: [Int!], $first: Int!, $skip: Int!) {
  vaults(first: $first, skip: $skip, where: { chainId_in: $chainIds }, orderBy: TotalAssetsUsd) {
    items {
      address
      symbol
      name
      whitelisted
      warnings { type level }
      chain { id network }
      asset { symbol address decimals }
      state {
        netApy
        totalAssets
        totalAssetsUsd
        allocation {
          market {
            loanAsset { symbol address }
            collateralAsset { symbol address }
          }
        }
      }
    }
  }
}
"""

CHAIN_MAP = {
    "ethereum": [1],
    "base": [8453],
    "arbitrum": [42161],
    "all": [1, 8453, 42161],
}

DEPOSIT_ALLOWLIST = {"USDC", "USDT", "ETH", "BTC"}
EXPOSURE_ALLOWLIST = {"BTC", "ETH", "WETH", "WBTC", "CBBTC", "CBETH", "WSTETH", "USDS", "SUSDS", "USDT", "USDC"}

chain = os.getenv("CHAIN", "all").lower()
limit = int(os.getenv("LIMIT", "10"))
first = int(os.getenv("FIRST", "200"))
skip = int(os.getenv("SKIP", "0"))
max_pages = int(os.getenv("MAX_PAGES", "0"))
chain_ids = CHAIN_MAP.get(chain)
if not chain_ids:
    raise SystemExit("Invalid CHAIN. Use: ethereum, base, arbitrum, all")

def infer_deposit_asset(symbol: str, name: str):
    merged = ((symbol or "") + " " + (name or "")).upper()
    if "USDC" in merged:
        return "USDC"
    if "USDT" in merged:
        return "USDT"
    if "WBTC" in merged or "CBBTC" in merged or "BTC" in merged:
        return "BTC"
    if "WSTETH" in merged or "CBETH" in merged or "WETH" in merged or "ETH" in merged:
        return "ETH"
    return None

def fetch(chain_id: int):
    items = []
    page = 0
    while True:
        if max_pages > 0 and page >= max_pages:
            print(f"Warning: chain {chain_id} hit MAX_PAGES={max_pages}. Consider increasing.", file=sys.stderr)
            break
        offset = skip + page * first
        payload = json.dumps({"query": QUERY, "variables": {"chainIds": [chain_id], "first": first, "skip": offset}}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.morpho.org/graphql",
            data=payload,
            headers={"content-type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
        if "errors" in data:
            raise RuntimeError(data["errors"])
        batch = data["data"]["vaults"]["items"]
        items.extend(batch)
        if len(batch) < first:
            break
        page += 1
    return items

items = []
for cid in chain_ids:
    items.extend(fetch(cid))

results = []
for v in items:
    if not v.get("whitelisted"):
        continue
    if v.get("warnings"):
        continue
    asset = v.get("asset") or {}
    deposit = (asset.get("symbol") or "").upper() or infer_deposit_asset(v.get("symbol"), v.get("name"))
    if deposit not in DEPOSIT_ALLOWLIST:
        continue

    state = v.get("state") or {}
    allocation = state.get("allocation") or []
    exposures = set()
    unknown_exposure = False
    for a in allocation:
        market = (a or {}).get("market") or {}
        for key in ("loanAsset", "collateralAsset"):
            sym = ((market.get(key) or {}).get("symbol") or "").upper()
            if not sym:
                unknown_exposure = True
                continue
            exposures.add(sym)
    if unknown_exposure or not exposures:
        continue
    if not exposures.issubset(EXPOSURE_ALLOWLIST):
        continue

    liquidity = state.get("totalAssetsUsd")
    if liquidity is None and deposit in ("USDC", "USDT"):
        decimals = asset.get("decimals") or 0
        total_assets = state.get("totalAssets")
        if total_assets is not None:
            liquidity = total_assets / (10 ** decimals)
    if liquidity is None or liquidity < 10_000_000:
        continue

    net_apy = state.get("netApy")
    if net_apy is None or net_apy <= 0:
        continue

    results.append({
        "name": v.get("name") or v.get("symbol"),
        "symbol": v.get("symbol"),
        "chain": (v.get("chain") or {}).get("network"),
        "deposit": deposit,
        "exposures": sorted(exposures),
        "net_apy_pct": net_apy * 100,
        "liquidity": liquidity,
        "address": v.get("address"),
    })

results.sort(key=lambda r: (-r["net_apy_pct"], -r["liquidity"]))
results = results[:limit]

ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
print("# Morpho Protocol Leaderboard (Conservative)")
print("")
print("> Top Vaults by Net APY")
print(f"> Chains: {chain.title()} | Updated: {ts}")
print("> Filters: Liquidity >$10M USD | whitelisted only | no warnings")
print("
---
")
print("## Top Vaults
")
print("| Rank | Vault | Deposit Asset | Chain | Net APY | Liquidity | Exposure | Link |")
print("|------|-------|---------------|-------|---------|-----------|----------|------|")
if not results:
    print("| - | No vaults matched filters | - | - | - | - | - | - |")
else:
    for i, r in enumerate(results, 1):
        chain_slug = (r['chain'] or '').lower()
        link = f"https://app.morpho.org/{chain_slug}/vault/{r['address']}"
        exposure_str = ", ".join(r["exposures"])
        print(f"| {i} | {r['name']} | {r['deposit']} | {r['chain']} | {r['net_apy_pct']:.2f}% | ${r['liquidity']/1e6:.1f}M | {exposure_str} | {link} |")
PY
```



## Output Format

```markdown
# Morpho Protocol Leaderboard (Conservative)

> Top Vaults by Net APY
> Chains: Ethereum, Base, Arbitrum | Updated: 2026-02-05 14:00 UTC
> Filters: Liquidity >$10M USD | whitelisted only | no warnings

---

## Top Vaults

| Rank | Vault | Deposit Asset | Chain | Net APY | Liquidity | Exposure | Link |
|------|-------|---------------|-------|---------|-----------|----------|------|
| 1 | Example Vault A | USDC | Ethereum | 4.75% | $43.4M | USDT, sUSDS | https://app.morpho.org/ethereum/vault/0x... |
| 2 | Example Vault B | ETH | Base | 3.92% | $32.1M | WETH, wstETH | https://app.morpho.org/base/vault/0x... |

---

### Summary

- Total Vaults: 2
- Average APY: 4.33%
- Highest APY: 4.75% (Example Vault A)

---

*Generated by Morpho Protocol Leaderboard*
*Data Source: Morpho GraphQL API*
```

## Error Handling

| Error | Action |
|-------|--------|
| GraphQL error | Return error payload and stop |
| API Timeout | Retry once with exponential backoff |
| Invalid Chain | Return valid options: ethereum, base, arbitrum, all |
| No Vaults Found | Return table with a single row: `No vaults matched filters` |

## Notes

- Exposure assets are enforced via V1 `state.allocation.market.loanAsset/collateralAsset`.
- `state.netApy` is a decimal rate; multiply by 100 for percentage output.
- Prefer `state.totalAssetsUsd` and fallback to `state.totalAssets / 10^decimals` for USDC/USDT only.
