import web3
from web3 import Web3
import requests
from django.conf import settings

# Try to import middleware with fallback
try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    try:
        # For older versions
        from web3.middleware import geth_poa_middleware
    except ImportError:
        # If all else fails, create a placeholder
        geth_poa_middleware = None

class CryptoPaymentHandler:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URI))
        
        # Inject POA middleware if available
        if geth_poa_middleware:
            try:
                self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            except (ValueError, AttributeError):
                try:
                    self.w3.middleware_onion.add(geth_poa_middleware)
                except:
                    pass
        else:
            # Try to inject by string name
            try:
                self.w3.middleware_onion.inject('geth_poa', layer=0)
            except:
                pass
    
    def create_usdt_payment(self, amount_usd, to_address, network='erc20'):
        """Create USDT payment."""
        # USDT contract addresses
        usdt_addresses = {
            'erc20': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
            'trc20': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'
        }
        
        if network == 'erc20':
            return self._create_erc20_payment(amount_usd, to_address, usdt_addresses['erc20'])
        elif network == 'trc20':
            return self._create_trc20_payment(amount_usd, to_address, usdt_addresses['trc20'])
    
    def _create_erc20_payment(self, amount_usd, to_address, contract_address):
        """Create ERC20 USDT payment."""
        # USDT has 6 decimals
        amount = int(amount_usd * 10**6)
        
        # Get contract
        contract = self.w3.eth.contract(
            address=contract_address,
            abi=self._get_erc20_abi()
        )
        
        # Create transaction
        transaction = contract.functions.transfer(
            to_address,
            amount
        ).build_transaction({
            'chainId': 1,
            'gas': 100000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(settings.ETH_WALLET_ADDRESS),
        })
        
        return transaction
    
    def _create_trc20_payment(self, amount_usd, to_address, contract_address):
        """Create TRC20 USDT payment."""
        # For TRC20, we'll use TronGrid API
        url = "https://api.trongrid.io/wallet/createtransaction"
        
        payload = {
            "to_address": to_address,
            "owner_address": settings.TRON_WALLET_ADDRESS,
            "contract_address": contract_address,
            "amount": int(amount_usd * 10**6)
        }
        
        response = requests.post(url, json=payload)
        return response.json()
    
    def verify_bitcoin_payment(self, transaction_hash, expected_amount):
        """Verify Bitcoin payment."""
        # Use blockchain.info API
        url = f"https://blockchain.info/rawtx/{transaction_hash}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            # Check confirmations and amount
            if data.get('block_height'):
                # Amount is in satoshis
                actual_amount = sum(out['value'] for out in data['out']) / 10**8
                return actual_amount >= expected_amount
        return False
    
    def get_crypto_exchange_rate(self, crypto, fiat='USD'):
        """Get cryptocurrency exchange rate."""
        # Use CoinGecko API
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': crypto,
            'vs_currencies': fiat.lower()
        }
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return data.get(crypto, {}).get(fiat.lower())
        return None
    
    def _get_erc20_abi(self):
        """Get ERC20 ABI."""
        return [
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]