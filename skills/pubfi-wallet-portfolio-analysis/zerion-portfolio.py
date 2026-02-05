#!/usr/bin/env python3
"""
Simple Zerion API client for fetching wallet portfolio.
Designed for use in skills execution.

Usage:
    python3 zerion-portfolio.py <wallet_address> [--only-defi]
    
Environment:
    ZERION_API_KEY - Required. Get from https://developers.zerion.io/
"""

import os
import sys
import json
import base64
import argparse
import requests


def get_portfolio(address, api_key, currency="usd", only_defi=False, non_trash=True):
    """
    Get wallet portfolio positions.
    
    Official endpoint: GET /v1/wallets/{address}/positions/
    Returns raw API response.
    
    By default, returns both wallet assets AND DeFi protocol positions.
    Use only_defi=True to get only DeFi protocol positions.
    """
    # Transform API key for Basic Auth (official method)
    api_key_transformed = base64.b64encode(f'{api_key}:'.encode()).decode()
    
    url = f'https://api.zerion.io/v1/wallets/{address}/positions/'
    headers = {
        'Authorization': f'Basic {api_key_transformed}',
        'accept': 'application/json'
    }
    
    params = {
        'currency': currency,
        'sort': 'value'
    }
    
    if non_trash:
        params['filter[trash]'] = 'only_non_trash'
    
    if only_defi:
        # Only get DeFi protocol positions
        params['filter[positions]'] = 'only_complex'
    
    all_data = []
    
    # Handle pagination
    while url:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        all_data.extend(data.get('data', []))
        
        # Get next page URL
        url = data.get('links', {}).get('next')
        params = None  # Params are in the next URL
    
    return all_data


def main():
    parser = argparse.ArgumentParser(
        description='Fetch wallet portfolio from Zerion API',
        epilog='API key must be set in ZERION_API_KEY environment variable'
    )
    parser.add_argument('address', help='EVM wallet address (0x...)')
    parser.add_argument('--only-defi', action='store_true', help='Only show DeFi protocol positions')
    parser.add_argument('--currency', default='usd', help='Currency for values (default: usd)')
    args = parser.parse_args()
    
    # Get API key from environment
    api_key = os.getenv('ZERION_API_KEY')
    if not api_key:
        print('ERROR: ZERION_API_KEY environment variable not set', file=sys.stderr)
        print('Get your API key at: https://developers.zerion.io/', file=sys.stderr)
        return 1
    
    try:
        # Fetch wallet and DeFi positions
        # Note: Zerion API separates wallet assets from DeFi protocol positions
        # We need to fetch both to get complete picture
        
        if args.only_defi:
            # Only get DeFi protocol positions
            data = get_portfolio(
                args.address, 
                api_key, 
                currency=args.currency,
                only_defi=True
            )
        else:
            # Get both wallet assets AND DeFi positions
            wallet_data = get_portfolio(
                args.address, 
                api_key, 
                currency=args.currency,
                only_defi=False
            )
            
            defi_data = get_portfolio(
                args.address, 
                api_key, 
                currency=args.currency,
                only_defi=True
            )
            
            # Combine both datasets
            data = wallet_data + defi_data
        
        # Process and summarize the data
        wallet_total = 0
        protocol_totals = {}
        token_values = {}
        
        for item in data:
            attrs = item.get('attributes', {})
            value = attrs.get('value')
            
            # Skip assets without value
            if value is None or value == 0:
                continue
            
            position_type = attrs.get('position_type', 'wallet')
            protocol = attrs.get('protocol')
            fungible = attrs.get('fungible_info', {})
            symbol = fungible.get('symbol', 'Unknown')
            
            # Categorize by wallet vs protocol
            # Protocol positions have position_type != 'wallet' AND protocol is not None
            if position_type != 'wallet' and protocol is not None:
                # This is a DeFi protocol position
                protocol_name = protocol if isinstance(protocol, str) else 'Unknown Protocol'
                protocol_totals[protocol_name] = protocol_totals.get(protocol_name, 0) + value
            else:
                # This is a wallet asset (includes LP tokens, aTokens, etc. in wallet)
                wallet_total += value
            
            # Aggregate by token symbol for top holdings
            token_values[symbol] = token_values.get(symbol, 0) + value
        
        # Calculate total portfolio value
        total_value = wallet_total + sum(protocol_totals.values())
        
        # Output summary
        print("=" * 60)
        print(f"Portfolio Summary for {args.address}")
        print("=" * 60)
        print()
        
        # 1. Asset Distribution by Type
        print("📊 Asset Distribution:")
        print(f"  Wallet Assets: ${wallet_total:,.2f} USD ({wallet_total/total_value*100:.1f}%)" if total_value > 0 else "  Wallet Assets: $0.00 USD")
        
        if protocol_totals:
            for protocol, value in sorted(protocol_totals.items(), key=lambda x: x[1], reverse=True):
                pct = (value / total_value * 100) if total_value > 0 else 0
                print(f"  {protocol}: ${value:,.2f} USD ({pct:.1f}%)")
        
        print(f"\n  Total: ${total_value:,.2f} USD")
        print()
        
        # 2. Top 20 Tokens (>$1)
        print("🏆 Top Holdings (>$1 USD):")
        
        # Filter tokens > $1 and sort by value
        top_tokens = [(symbol, value) for symbol, value in token_values.items() if value > 1]
        top_tokens.sort(key=lambda x: x[1], reverse=True)
        top_tokens = top_tokens[:20]
        
        if top_tokens:
            for symbol, value in top_tokens:
                pct = (value / total_value * 100) if total_value > 0 else 0
                print(f"  {symbol:<15} ${value:>12,.2f} USD  ({pct:>5.1f}%)")
        else:
            print("  No assets over $1 USD found")
        
        print()
        print("=" * 60)
            
    except requests.exceptions.HTTPError as e:
        print(f'HTTP Error: {e}', file=sys.stderr)
        if e.response.status_code == 401:
            print('Invalid API key. Check your ZERION_API_KEY.', file=sys.stderr)
        return 1
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
