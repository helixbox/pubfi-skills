import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

GRAPHQL = "https://api.morpho.org/graphql"

VAULTS_QUERY = """
query VaultV2s($chainIds: [Int!], $first: Int!, $skip: Int!) {
  vaultV2s(
    where: { chainId_in: $chainIds }
    first: $first
    skip: $skip
    orderBy: TotalAssetsUsd
    orderDirection: Desc
  ) {
    items {
      address
      name
      symbol
      chain { id network }
      asset { address symbol decimals }
      totalAssets
      totalAssetsUsd
      netApy
      whitelisted
      warnings { type level }
    }
    pageInfo { countTotal count skip limit }
  }
}
"""

EXPOSURE_QUERY = """
query VaultV2Exposure($address: String!, $chainId: Int!, $positionsFirst: Int!) {
  vaultV2ByAddress(address: $address, chainId: $chainId) {
    adapters {
      items {
        __typename
        type
        ... on MetaMorphoAdapter {
          metaMorpho {
            address
            asset { address symbol }
          }
        }
        ... on MorphoMarketV1Adapter {
          positions(first: $positionsFirst) {
            items {
              market {
                loanAsset { address symbol }
                collateralAsset { address symbol }
              }
            }
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

ALLOWLIST = {
    1: {
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
        "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH",
        "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "WBTC",
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": "CBBTC",
        "0xbe9895146f7af43049ca1c1ae358b0541ea49704": "CBETH",
        "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": "WSTETH",
        "0xdc035d45d973e3ec169d2276ddab16f1e407384f": "USDS",
        "0xa3931d71877c0e7a3148cb7eb4463524fec27fbd": "SUSDS",
    },
    8453: {
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": "USDC",
        "0xfde4c96c8593536e31f229ea8f37b2ada2699bb2": "USDT",
        "0x4200000000000000000000000000000000000006": "WETH",
        "0x0555e30da8f98308edb960aa94c0db47230d2b9c": "WBTC",
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": "CBBTC",
        "0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22": "CBETH",
        "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452": "WSTETH",
        "0x820c137fa70c8691f0e44dc420a5e53c168921dc": "USDS",
        "0x5875eee11cf8398102fdad704c9e96607675467a": "SUSDS",
    },
    42161: {
        "0xaf88d065e77c8cc2239327c5edb3a432268e5831": "USDC",
        "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9": "USDT",
        "0x82af49447d8a07e3bd95bd0d56f35241523fbab1": "WETH",
        "0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f": "WBTC",
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": "CBBTC",
        "0x1debd73e752beaf79865fd6446b0c970eae7732f": "CBETH",
        "0x5979d7b546e38e414f7e9822514be443a4800529": "WSTETH",
    },
}

DEPOSIT_ALLOW = {"USDC", "USDT", "ETH", "BTC"}

chain = os.getenv("CHAIN", "all").lower()
limit = int(os.getenv("LIMIT", "10"))
first = int(os.getenv("FIRST", "500"))
skip = int(os.getenv("SKIP", "0"))
positions_first = int(os.getenv("POSITIONS_FIRST", "50"))
request_delay_ms = int(os.getenv("REQUEST_DELAY_MS", "0"))

chain_ids = CHAIN_MAP.get(chain)
if not chain_ids:
    raise SystemExit("Invalid CHAIN. Use: ethereum, base, arbitrum, all")

limit = max(1, min(limit, 100))


def gql(query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(GRAPHQL, data=payload, headers={"content-type": "application/json"})
    for attempt in range(2):
        try:
            if request_delay_ms > 0:
                time.sleep(request_delay_ms / 1000)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            if "errors" in data:
                raise RuntimeError(data["errors"])
            return data["data"]
        except urllib.error.HTTPError as e:
            if e.code in (500, 502, 503, 504) and attempt == 0:
                time.sleep(1.5 + (attempt * 0.5))
                continue
            raise
        except urllib.error.URLError:
            if attempt == 0:
                time.sleep(1.5 + (attempt * 0.5))
                continue
            raise


def canonical_deposit(symbol: str) -> str:
    if symbol == "WETH":
        return "ETH"
    if symbol in ("WBTC", "CBBTC"):
        return "BTC"
    return symbol


def fetch_vaults(chain_id: int):
    items = []
    page = 0
    page_size = first
    while True:
        offset = skip + page * page_size
        try:
            data = gql(VAULTS_QUERY, {"chainIds": [chain_id], "first": page_size, "skip": offset})
        except urllib.error.HTTPError as e:
            if e.code in (500, 502, 503, 504) and page_size > 50:
                new_size = max(50, page_size // 2)
                print(f"Warning: vault list query failed on chain {chain_id} with page size {page_size}; retrying with {new_size}", file=sys.stderr)
                page_size = new_size
                items = []
                page = 0
                continue
            raise
        batch = data["vaultV2s"]["items"]
        items.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return items


exposure_cache = {}


def resolve_exposures(vault_address: str, chain_id: int, seen=None, positions_limit=None):
    key = (chain_id, vault_address.lower())
    if key in exposure_cache:
        return exposure_cache[key]
    if seen is None:
        seen = set()
    if key in seen:
        exposure_cache[key] = (set(), True)
        return exposure_cache[key]
    seen.add(key)

    if positions_limit is None:
        positions_limit = positions_first

    try:
        data = gql(EXPOSURE_QUERY, {"address": vault_address, "chainId": chain_id, "positionsFirst": positions_limit})
    except Exception as exc:
        if positions_limit > 25:
            fallback = max(25, positions_limit // 2)
            print(f"Warning: exposure query failed for {vault_address} on {chain_id}: {exc}; retrying with positionsFirst={fallback}", file=sys.stderr)
            return resolve_exposures(vault_address, chain_id, seen=seen, positions_limit=fallback)
        print(f"Warning: exposure query failed for {vault_address} on {chain_id}: {exc}", file=sys.stderr)
        exposure_cache[key] = (set(), True)
        return exposure_cache[key]

    vault = data.get("vaultV2ByAddress") or {}
    adapters = (vault.get("adapters") or {}).get("items") or []

    exposures = set()
    unknown = False

    for adapter in adapters:
        typename = adapter.get("__typename")
        if typename == "MetaMorphoAdapter":
            meta = adapter.get("metaMorpho") or {}
            meta_addr = (meta.get("address") or "").lower()
            asset_addr = ((meta.get("asset") or {}).get("address") or "").lower()
            if meta_addr:
                nested, nested_unknown = resolve_exposures(meta_addr, chain_id, seen)
                if not nested_unknown:
                    exposures.update(nested)
                    continue
            if asset_addr:
                exposures.add(asset_addr)
                print(f"Warning: MetaMorpho fallback to asset address for {meta_addr or vault_address}", file=sys.stderr)
                continue
            unknown = True
        elif typename == "MorphoMarketV1Adapter":
            positions = (adapter.get("positions") or {}).get("items") or []
            if len(positions) >= positions_limit:
                unknown = True
                continue
            for pos in positions:
                market = (pos or {}).get("market") or {}
                for key in ("loanAsset", "collateralAsset"):
                    addr = ((market.get(key) or {}).get("address") or "").lower()
                    if not addr:
                        unknown = True
                        continue
                    exposures.add(addr)
        else:
            unknown = True

    if not exposures:
        unknown = True

    exposure_cache[key] = (exposures, unknown)
    return exposure_cache[key]


results = []
for cid in chain_ids:
    allow = ALLOWLIST.get(cid, {})
    for v in fetch_vaults(cid):
        if not v.get("whitelisted"):
            continue
        if v.get("warnings"):
            continue

        asset = v.get("asset") or {}
        deposit_addr = (asset.get("address") or "").lower()
        deposit_symbol = allow.get(deposit_addr)
        if not deposit_symbol:
            continue
        deposit_canon = canonical_deposit(deposit_symbol)
        if deposit_canon not in DEPOSIT_ALLOW:
            continue

        liquidity = v.get("totalAssetsUsd")
        if liquidity is None and deposit_canon in ("USDC", "USDT"):
            total_assets = v.get("totalAssets")
            decimals = asset.get("decimals") or 0
            if total_assets is not None:
                liquidity = total_assets / (10 ** decimals)
        if liquidity is None or liquidity < 10_000_000:
            continue

        net_apy = v.get("netApy")
        if net_apy is None or net_apy <= 0:
            continue

        exposures, unknown = resolve_exposures(v.get("address"), cid)
        if unknown:
            continue
        if not exposures.issubset(set(allow.keys())):
            continue

        exposure_symbols = sorted({allow[a] for a in exposures if a in allow})
        results.append({
            "name": v.get("name") or v.get("symbol") or v.get("address"),
            "symbol": v.get("symbol"),
            "chain": (v.get("chain") or {}).get("network"),
            "deposit": deposit_canon,
            "exposures": exposure_symbols,
            "net_apy_pct": net_apy * 100,
            "liquidity": liquidity,
            "address": v.get("address"),
        })

results.sort(key=lambda r: (-r["net_apy_pct"], -r["liquidity"]))
results = results[:limit]

print("# Morpho Protocol Leaderboard (Conservative)")
print("")
print("> Top Vaults by Net APY")
print(f"> Chains: {chain.title()} | Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
print("> Filters: Liquidity >$10M USD | whitelisted only | no warnings")
print("\n---\n")
print("## Top Vaults\n")
print("| Rank | Vault | Deposit Asset | Chain | Net APY | Liquidity | Exposure | Link |")
print("|------|-------|---------------|-------|---------|-----------|----------|------|")
if not results:
    print("| - | No vaults matched filters | - | - | - | - | - | - |")
else:
    for i, r in enumerate(results, 1):
        chain_slug = (r["chain"] or "").lower()
        link = f"https://app.morpho.org/{chain_slug}/vault/{r['address']}"
        exposure_str = ", ".join(r["exposures"]) if r["exposures"] else "-"
        print(f"| {i} | {r['name']} | {r['deposit']} | {r['chain']} | {r['net_apy_pct']:.2f}% | ${r['liquidity']/1e6:.1f}M | {exposure_str} | {link} |")
