# ============================================================
# teerpay_conditional_bot.py — TeerPay Conditional Payment Bot
# Arc Testnet | Python | web3.py
#
# "Programmable Money Flow" — kirim USDC hanya jika:
#   1. FX Rate menguntungkan (USD kuat vs mata uang tujuan)
#   2. Waktu sesuai jadwal (hari kerja, jam 08-22 WIB)
#   3. Saldo cukup (di atas minimum + reserve)
#
# Analogi trading bot:
#   conditions.py    = strategy signals (semua harus agree)
#   evaluate_all()   = confluence filter sebelum entry
#   send_remittance  = execute order
#   CHECK_INTERVAL   = trading loop / cron
# ============================================================

import time
import sys
import logging
import json
import csv
import os
from datetime import datetime
from web3 import Web3
from dotenv import load_dotenv

from conditional_config import (
    ARC_RPC_URL, ARC_CHAIN_ID, ARC_EXPLORER,
    USDC_CONTRACT, TEERPAY_CONTRACT, USDC_DECIMALS,
    PRIVATE_KEY, WALLET_ADDRESS,
    FX_THRESHOLDS, ALLOWED_DAYS, ALLOWED_HOURS,
    MIN_RESERVE_USDC, DELAY_BETWEEN_TX, CHECK_INTERVAL,
    REMITTANCE_TARGETS,
)
from conditions import evaluate_all_conditions

load_dotenv()

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("teerpay_conditional.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("TeerPayBot")

# ── ABIs ─────────────────────────────────────────────────────
USDC_ABI = [
    {"name": "approve",   "type": "function", "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable"},
    {"name": "allowance", "type": "function", "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view"},
    {"name": "balanceOf", "type": "function", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view"},
]
TEERPAY_ABI = [
    {"name": "sendRemittance", "type": "function", "inputs": [{"name": "recipient", "type": "address"}, {"name": "amount", "type": "uint256"}, {"name": "country", "type": "string"}, {"name": "currency", "type": "string"}, {"name": "memo", "type": "string"}], "outputs": [], "stateMutability": "nonpayable"},
    {"name": "getStats", "type": "function", "inputs": [], "outputs": [{"name": "_totalVolume", "type": "uint256"}, {"name": "_totalTxCount", "type": "uint256"}, {"name": "_minAmount", "type": "uint256"}, {"name": "_maxAmount", "type": "uint256"}, {"name": "_paused", "type": "bool"}], "stateMutability": "view"},
]


# ── Web3 Setup ────────────────────────────────────────────────
def get_web3() -> Web3:
    w3 = Web3(Web3.HTTPProvider(ARC_RPC_URL))
    if not w3.is_connected():
        raise ConnectionError(f"Gagal konek ke Arc Testnet: {ARC_RPC_URL}")
    return w3

def get_usdc_balance(w3: Web3, address: str = None) -> float:
    addr = Web3.to_checksum_address(address or WALLET_ADDRESS)
    raw  = w3.eth.contract(address=Web3.to_checksum_address(USDC_CONTRACT), abi=USDC_ABI).functions.balanceOf(addr).call()
    return raw / (10 ** USDC_DECIMALS)

def approve_if_needed(w3: Web3, amount_raw: int):
    account  = w3.eth.account.from_key(PRIVATE_KEY)
    sender   = Web3.to_checksum_address(account.address)
    usdc     = w3.eth.contract(address=Web3.to_checksum_address(USDC_CONTRACT), abi=USDC_ABI)
    allowance = usdc.functions.allowance(sender, Web3.to_checksum_address(TEERPAY_CONTRACT)).call()
    if allowance >= amount_raw:
        return None
    nonce  = w3.eth.get_transaction_count(sender)
    tx     = usdc.functions.approve(Web3.to_checksum_address(TEERPAY_CONTRACT), amount_raw * 100).build_transaction({"chainId": ARC_CHAIN_ID, "nonce": nonce, "gas": 80_000, "gasPrice": w3.eth.gas_price, "from": sender})
    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    th     = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(th, timeout=60)
    return th.hex()

def send_remittance(w3: Web3, target: dict, memo: str) -> dict:
    account    = w3.eth.account.from_key(PRIVATE_KEY)
    sender     = Web3.to_checksum_address(account.address)
    to         = Web3.to_checksum_address(target["address"])
    amount_raw = int(target["amount"] * (10 ** USDC_DECIMALS))
    approve_if_needed(w3, amount_raw)
    teerpay = w3.eth.contract(address=Web3.to_checksum_address(TEERPAY_CONTRACT), abi=TEERPAY_ABI)
    nonce   = w3.eth.get_transaction_count(sender)
    tx      = teerpay.functions.sendRemittance(to, amount_raw, target["country"], target["currency"], memo).build_transaction({"chainId": ARC_CHAIN_ID, "nonce": nonce, "gas": 150_000, "gasPrice": w3.eth.gas_price, "from": sender})
    signed  = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    th      = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(th, timeout=60)
    return {
        "tx_hash":  th.hex(),
        "status":   "success" if receipt.status == 1 else "failed",
        "gas_used": receipt.gasUsed,
        "block":    receipt.blockNumber,
        "explorer": f"{ARC_EXPLORER}/tx/0x{th.hex()}",
        "amount":   target["amount"],
        "country":  target["country"],
        "memo":     memo,
    }

def log_to_csv(result: dict, condition_result: dict):
    file   = "conditional_transactions.csv"
    exists = os.path.isfile(file)
    with open(file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp","country","amount","status","tx_hash","fx_rate","fx_currency","schedule_ok","balance_ok","explorer"])
        if not exists:
            writer.writeheader()
        conds = condition_result["conditions"]
        writer.writerow({
            "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "country":     result.get("country",""),
            "amount":      result.get("amount",""),
            "status":      result.get("status",""),
            "tx_hash":     result.get("tx_hash",""),
            "fx_rate":     conds["fx_rate"]["current"],
            "fx_currency": conds["fx_rate"]["currency"],
            "schedule_ok": conds["schedule"]["passed"],
            "balance_ok":  conds["balance"]["passed"],
            "explorer":    result.get("explorer",""),
        })


# ── ONE CYCLE ─────────────────────────────────────────────────
def run_cycle(w3: Web3, cycle_num: int = 1):
    """
    Satu siklus evaluasi + eksekusi.
    Analogi: satu iterasi trading loop
    """
    log.info("=" * 60)
    log.info(f"  CYCLE #{cycle_num} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}")
    log.info("=" * 60)

    balance = get_usdc_balance(w3)
    log.info(f"  Wallet balance: {balance:.4f} USDC")

    sent_count = 0
    skip_count = 0
    results    = []

    for target in REMITTANCE_TARGETS:
        country = target["country"]
        amount  = target["amount"]

        log.info(f"\n  [{country}] Evaluating conditions...")

        # Evaluate semua kondisi
        eval_result = evaluate_all_conditions(
            country        = country,
            current_balance= balance,
            amount_to_send = amount,
            fx_thresholds  = FX_THRESHOLDS,
            allowed_days   = ALLOWED_DAYS,
            allowed_hours  = ALLOWED_HOURS,
            min_reserve    = MIN_RESERVE_USDC,
        )

        log.info(f"  Result: {eval_result['summary']}")

        if not eval_result["go"]:
            skip_count += 1
            log.info(f"  ⏸ SKIPPED — conditions not met")
            continue

        # Semua kondisi pass → kirim!
        memo = (
            f"TeerPay|Conditional|{country}|"
            f"{target['currency']}|{amount}USDC|"
            f"FX={eval_result['conditions']['fx_rate']['current']:.0f}|"
            f"{datetime.now().strftime('%Y%m%d')}"
        )

        log.info(f"  🚀 All conditions met — sending {amount} USDC to {country}...")
        log.info(f"  Memo: {memo}")

        try:
            tx_result = send_remittance(w3, target, memo)
            results.append({**tx_result, **{"condition_result": eval_result}})

            if tx_result["status"] == "success":
                sent_count += 1
                balance    -= amount  # update balance lokal
                log.info(f"  ✅ SENT! TX: {tx_result['explorer']}")
                log.info(f"  Gas used: {tx_result['gas_used']} | Block: #{tx_result['block']}")
                log_to_csv(tx_result, eval_result)
            else:
                log.error(f"  ❌ FAILED! Hash: {tx_result['tx_hash']}")

        except Exception as e:
            log.error(f"  ❌ ERROR: {e}")
            skip_count += 1

        if target != REMITTANCE_TARGETS[-1]:
            time.sleep(DELAY_BETWEEN_TX)

    # Cycle summary
    log.info(f"\n  Cycle #{cycle_num} done: {sent_count} sent, {skip_count} skipped")
    log.info(f"  Balance remaining: {get_usdc_balance(w3):.4f} USDC")
    return results


# ── MAIN — TWO MODES ─────────────────────────────────────────

def run_once():
    """Mode lokal: jalankan satu kali, keluar."""
    log.info("TeerPay Conditional Bot — SINGLE RUN MODE")
    w3 = get_web3()
    log.info(f"Connected to Arc Testnet | Block: #{w3.eth.block_number}")
    run_cycle(w3, cycle_num=1)
    log.info("Done. Check conditional_transactions.csv for history.")


def run_loop():
    """
    Mode cloud: jalan terus, cek kondisi setiap CHECK_INTERVAL detik.
    Analogi: trading bot yang running 24/7
    """
    log.info("TeerPay Conditional Bot — LOOP MODE (24/7)")
    log.info(f"Check interval: every {CHECK_INTERVAL//60} minutes")

    w3       = get_web3()
    cycle    = 1

    while True:
        try:
            run_cycle(w3, cycle_num=cycle)
            cycle += 1
        except Exception as e:
            log.error(f"Cycle error: {e}")

        log.info(f"Next check in {CHECK_INTERVAL//60} minutes...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    if not PRIVATE_KEY:
        log.error("PRIVATE_KEY tidak ditemukan di .env!")
        sys.exit(1)

    mode = sys.argv[1] if len(sys.argv) > 1 else "once"

    if mode == "loop":
        run_loop()
    else:
        run_once()
