#!/usr/bin/env node

/**
 * PubFi WalletConnect Transactions
 * 
 * This script enables users to connect their wallet via WalletConnect and execute
 * blockchain transactions.
 * 
 * Usage:
 *   import { WalletConnectTransactionManager } from './walletconnect_transactions';
 *   const manager = new WalletConnectTransactionManager('ethereum');
 *   await manager.connect();
 *   const result = await manager.sendTransaction({ to: '0x...', value: ethers.parseEther('0.01') });
 * 
 * Environment Variables:
 *   WALLETCONNECT_PROJECT_ID - Required: WalletConnect Cloud project ID
 */

import SignClient from '@walletconnect/sign-client';
import { SessionTypes } from '@walletconnect/types';
import { ethers } from 'ethers';
import * as QRCode from 'qrcode-terminal';
import * as dotenv from 'dotenv';

dotenv.config();

// Configuration
const WALLETCONNECT_PROJECT_ID = process.env.WALLETCONNECT_PROJECT_ID;
const CONNECTION_TIMEOUT = parseInt(process.env.CONNECTION_TIMEOUT || '300000'); // 5 minutes

// Chain configurations
const CHAINS: Record<string, { chainId: string; name: string; rpcUrl: string; explorer: string }> = {
  ethereum: {
    chainId: 'eip155:1',
    name: 'Ethereum Mainnet',
    rpcUrl: process.env.RPC_ENDPOINT_ETHEREUM || 'https://eth.llamarpc.com',
    explorer: 'https://etherscan.io'
  },
  polygon: {
    chainId: 'eip155:137',
    name: 'Polygon',
    rpcUrl: 'https://polygon-rpc.com',
    explorer: 'https://polygonscan.com'
  },
  arbitrum: {
    chainId: 'eip155:42161',
    name: 'Arbitrum One',
    rpcUrl: 'https://arb1.arbitrum.io/rpc',
    explorer: 'https://arbiscan.io'
  },
  optimism: {
    chainId: 'eip155:10',
    name: 'Optimism',
    rpcUrl: 'https://mainnet.optimism.io',
    explorer: 'https://optimistic.etherscan.io'
  },
  base: {
    chainId: 'eip155:8453',
    name: 'Base',
    rpcUrl: 'https://mainnet.base.org',
    explorer: 'https://basescan.org'
  }
};

// Transaction result type
interface TransactionResult {
  success: boolean;
  txHash?: string;
  blockNumber?: number;
  gasUsed?: string;
  error?: string;
  receipt?: ethers.TransactionReceipt;
}

class WalletConnectTransactionManager {
  private signClient?: SignClient;
  private session?: SessionTypes.Struct;
  private provider?: ethers.JsonRpcProvider;
  private walletAddress?: string;
  private chainConfig: typeof CHAINS[keyof typeof CHAINS];

  constructor(chain: string = 'ethereum') {
    if (!CHAINS[chain]) {
      throw new Error(`Unsupported chain: ${chain}. Supported: ${Object.keys(CHAINS).join(', ')}`);
    }
    this.chainConfig = CHAINS[chain];
    this.provider = new ethers.JsonRpcProvider(this.chainConfig.rpcUrl);
  }

  /**
   * Initialize WalletConnect and establish session
   */
  async connect(): Promise<string> {
    if (!WALLETCONNECT_PROJECT_ID) {
      throw new Error(
        'WALLETCONNECT_PROJECT_ID environment variable not set.\n' +
        'Get your project ID from: https://cloud.walletconnect.com/'
      );
    }

    console.log('🔗 Initializing WalletConnect...\n');

    // Initialize SignClient
    this.signClient = await SignClient.init({
      projectId: WALLETCONNECT_PROJECT_ID,
      metadata: {
        name: 'WalletConnect Transactions',
        description: 'Execute blockchain transactions via WalletConnect',
        url: 'https://test.com',
        icons: ['https://walletconnect.com/walletconnect-logo.png']
      }
    });

    // Create pairing and get URI
    const { uri, approval } = await this.signClient.connect({
      requiredNamespaces: {
        eip155: {
          methods: [
            'eth_sendTransaction',
            'eth_signTransaction',
            'eth_sign',
            'personal_sign',
            'eth_signTypedData'
          ],
          chains: [this.chainConfig.chainId],
          events: ['chainChanged', 'accountsChanged']
        }
      }
    });

    if (!uri) {
      throw new Error('Failed to generate WalletConnect URI');
    }

    // Display QR code
    console.log('📱 Scan this QR code with your wallet:\n');
    QRCode.generate(uri, { small: true });
    console.log(`\nOr use this URI: ${uri}\n`);
    console.log(`⏳ Waiting for wallet connection (timeout: ${CONNECTION_TIMEOUT / 1000}s)...\n`);

    // Wait for session approval with timeout
    const timeoutPromise = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('Connection timeout')), CONNECTION_TIMEOUT)
    );

    try {
      this.session = await Promise.race([approval(), timeoutPromise]);
      
      // Extract wallet address
      const accounts = this.session.namespaces.eip155?.accounts || [];
      if (accounts.length === 0) {
        throw new Error('No accounts found in session');
      }

      // Format: eip155:1:0x123... -> extract 0x123...
      this.walletAddress = accounts[0].split(':')[2];

      console.log(`✅ Wallet connected successfully!`);
      console.log(`📍 Address: ${this.walletAddress}`);
      console.log(`🌐 Network: ${this.chainConfig.name}\n`);

      return this.walletAddress;
    } catch (error) {
      if (error instanceof Error && error.message === 'Connection timeout') {
        throw new Error(
          'Connection timeout. Please ensure:\n' +
          '1. Your wallet app is open\n' +
          '2. You scanned the QR code\n' +
          '3. You approved the connection'
        );
      }
      throw error;
    }
  }

  /**
   * Get connected wallet address
   */
  getWalletAddress(): string | undefined {
    return this.walletAddress;
  }

  /**
   * Get chain configuration
   */
  getChainConfig() {
    return this.chainConfig;
  }

  /**
   * Send transaction via WalletConnect
   * Accepts standard ethers.TransactionRequest
   */
  async sendTransaction(tx: ethers.TransactionRequest): Promise<TransactionResult> {
    if (!this.signClient || !this.session || !this.walletAddress) {
      throw new Error('Not connected');
    }

    try {
      // Set from address if not provided
      if (!tx.from) {
        tx.from = this.walletAddress;
      }

      // Set chainId if not provided
      if (!tx.chainId) {
        tx.chainId = parseInt(this.chainConfig.chainId.split(':')[1]);
      }

      // Estimate gas if not provided
      if (!tx.gasLimit && this.provider) {
        tx.gasLimit = await this.provider.estimateGas(tx);
      }

      // Get gas price if not provided
      if (!tx.gasPrice && !tx.maxFeePerGas && this.provider) {
        const feeData = await this.provider.getFeeData();
        tx.gasPrice = feeData.gasPrice || undefined;
      }

      console.log('📋 Transaction Summary:');
      console.log('─'.repeat(50));
      console.log(`From:        ${tx.from}`);
      console.log(`To:          ${tx.to}`);
      console.log(`Value:       ${tx.value ? ethers.formatEther(tx.value) : '0'} ETH`);
      console.log(`Gas Limit:   ${tx.gasLimit?.toString() || 'auto'}`);
      console.log('─'.repeat(50));
      console.log('\n📱 Please approve the transaction in your wallet...\n');

      // Prepare transaction params for WalletConnect
      const txParams: any = {
        from: tx.from,
        to: tx.to,
        data: tx.data || '0x'
      };

      if (tx.value) {
        txParams.value = `0x${BigInt(tx.value.toString()).toString(16)}`;
      }

      if (tx.gasLimit) {
        txParams.gasLimit = `0x${BigInt(tx.gasLimit.toString()).toString(16)}`;
      }

      if (tx.gasPrice) {
        txParams.gasPrice = `0x${BigInt(tx.gasPrice.toString()).toString(16)}`;
      }

      if (tx.maxFeePerGas) {
        txParams.maxFeePerGas = `0x${BigInt(tx.maxFeePerGas.toString()).toString(16)}`;
      }

      if (tx.maxPriorityFeePerGas) {
        txParams.maxPriorityFeePerGas = `0x${BigInt(tx.maxPriorityFeePerGas.toString()).toString(16)}`;
      }

      // Send transaction request via WalletConnect
      const txHash = await this.signClient.request<string>({
        topic: this.session.topic,
        chainId: this.chainConfig.chainId,
        request: {
          method: 'eth_sendTransaction',
          params: [txParams]
        }
      });

      console.log(`✅ Transaction sent!`);
      console.log(`📝 Hash: ${txHash}\n`);

      // Wait for transaction confirmation if provider is available
      if (this.provider) {
        console.log(`⏳ Waiting for confirmation...\n`);
        const receipt = await this.provider.waitForTransaction(txHash, 1);

        if (!receipt) {
          throw new Error('Transaction receipt not found');
        }

        console.log(`✅ Transaction confirmed!`);
        console.log(`📦 Block: ${receipt.blockNumber}`);
        console.log(`⛽ Gas used: ${receipt.gasUsed.toString()}\n`);

        return {
          success: true,
          txHash,
          blockNumber: receipt.blockNumber,
          gasUsed: receipt.gasUsed.toString(),
          receipt
        };
      }

      // If no provider, return basic result
      return {
        success: true,
        txHash
      };
    } catch (error) {
      if (error instanceof Error) {
        if (error.message.includes('User rejected')) {
          return {
            success: false,
            error: 'User rejected the transaction in wallet'
          };
        }
        return {
          success: false,
          error: error.message
        };
      }
      return {
        success: false,
        error: 'Unknown error occurred'
      };
    }
  }

  /**
   * Generate markdown report
   */
  generateReport(result: TransactionResult, txRequest?: ethers.TransactionRequest): string {
    const timestamp = new Date().toISOString();
    const status = result.success ? 'SUCCESS' : 'FAILED';
    const explorerUrl = result.txHash
      ? `${this.chainConfig.explorer}/tx/${result.txHash}`
      : 'N/A';

    let report = `# WalletConnect Transaction Report\n\n`;
    report += `> **Chain**: ${this.chainConfig.name} | **Wallet**: ${this.walletAddress} | **Status**: ${status}\n`;
    report += `> **Timestamp**: ${timestamp}\n\n`;
    report += `---\n\n`;
    report += `## Transaction Details\n\n`;
    report += `| Field | Value |\n`;
    report += `|-------|-------|\n`;
    report += `| **From** | ${this.walletAddress} |\n`;
    
    if (result.success) {
      if (txRequest?.to) {
        report += `| **To** | ${txRequest.to} |\n`;
      }
      if (txRequest?.value) {
        report += `| **Value** | ${ethers.formatEther(txRequest.value)} ETH |\n`;
      }
      report += `| **Gas Used** | ${result.gasUsed || 'N/A'} |\n`;
      report += `| **Transaction Hash** | ${result.txHash} |\n`;
      report += `| **Block Number** | ${result.blockNumber || 'Pending'} |\n`;
      report += `\n**Block Explorer**: [View Transaction](${explorerUrl})\n\n`;
    } else {
      report += `| **Error** | ${result.error} |\n\n`;
    }

    report += `---\n\n`;
    report += `## Summary\n\n`;
    
    if (result.success) {
      report += `Successfully executed transaction on ${this.chainConfig.name}\n\n`;
      report += `- **Executed At**: ${timestamp}\n`;
    } else {
      report += `Transaction failed: ${result.error}\n\n`;
    }

    report += `---\n\n`;
    report += `*Generated by PubFi WalletConnect Transactions*\n`;

    return report;
  }

  /**
   * Disconnect session
   */
  async disconnect(): Promise<void> {
    if (this.signClient && this.session) {
      await this.signClient.disconnect({
        topic: this.session.topic,
        reason: {
          code: 6000,
          message: 'User disconnected'
        }
      });
      console.log('👋 Disconnected from wallet\n');
    }
  }
}

export { WalletConnectTransactionManager, TransactionResult, CHAINS };
