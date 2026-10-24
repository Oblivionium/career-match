"""Agent Payment Protocol (seller role) for the paid Application Pack.

Flow inside ASI:One:
  coordinator --RequestPayment--> user (ASI:One shows the pay UI, user pays testnet FET)
  user --CommitPayment(tx hash)--> coordinator   -> we verify the transfer on-chain
  coordinator --CompletePayment--> user, then delivers the pack
  (or CancelPayment if verification fails; RejectPayment from the user if they decline)
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

import httpx
from uagents import Context, Protocol
from uagents_core.contrib.protocols.payment import (
    CancelPayment,
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)

from shared import config

log = logging.getLogger(__name__)

payment_proto = Protocol(spec=payment_protocol_spec, role="seller")

# Wired up by coordinator/agent.py so this module doesn't import the chat logic.
on_paid: Callable[[Context, str, dict], Awaitable[None]] | None = None
on_declined: Callable[[Context, str, dict, str], Awaitable[None]] | None = None

DENOM = "atestfet" if config.FET_USE_TESTNET else "afet"
REST_URL = "https://rest-dorado.fetch.ai" if config.FET_USE_TESTNET else "https://rest-fetchhub.fetch.ai"


def recipient_wallet(ctx: Context) -> str:
    if config.PAYMENT_WALLET:
        return config.PAYMENT_WALLET
    return str(ctx.agent.wallet.address())


def to_base_units(amount_fet: str) -> int:
    whole, _, frac = amount_fet.partition(".")
    frac = (frac + "0" * 18)[:18]
    return int(whole or "0") * 10**18 + int(frac or "0")


async def request_pack_payment(ctx: Context, user: str, job_id: str, job_title: str) -> str:
    reference = str(uuid.uuid4())
    ctx.storage.set(f"payref:{reference}", {"user": user, "job_id": job_id})
    req = RequestPayment(
        accepted_funds=[Funds(amount=config.PACK_PRICE_FET, currency="FET", payment_method="fet_direct")],
        recipient=recipient_wallet(ctx),
        deadline_seconds=600,
        reference=reference,
        description=f"Application Pack for '{job_title[:60]}': tailored cover letter, resume bullets, gap plan",
        metadata={
            "service": "application_pack",
            "fet_network": "stable-testnet" if config.FET_USE_TESTNET else "mainnet",
            "content": "Pay to unlock your tailored Application Pack.",
        },
    )
    await ctx.send(user, req)
    return reference


def _transfer_matches(attrs: dict[str, str], recipient: str, min_amount: int) -> bool:
    if attrs.get("recipient") != recipient:
        return False
    for part in attrs.get("amount", "").split(","):
        part = part.strip()
        if part.endswith(DENOM):
            try:
                if int(part[: -len(DENOM)]) >= min_amount:
                    return True
            except ValueError:
                continue
    return False


async def _verify_via_rest(tx_hash: str, recipient: str, min_amount: int) -> bool:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{REST_URL}/cosmos/tx/v1beta1/txs/{tx_hash}")
        r.raise_for_status()
        tx = r.json()["tx_response"]
    if int(tx.get("code", 1)) != 0:
        return False
    for ev in tx.get("events", []):
        if ev.get("type") == "transfer":
            attrs = {a.get("key"): a.get("value") for a in ev.get("attributes", [])}
            if _transfer_matches(attrs, recipient, min_amount):
                return True
    return False


def _verify_via_grpc(tx_hash: str, recipient: str, min_amount: int) -> bool:
    from cosmpy.aerial.client import LedgerClient
    from cosmpy.aerial.config import NetworkConfig

    net = NetworkConfig.fetchai_stable_testnet() if config.FET_USE_TESTNET else NetworkConfig.fetchai_mainnet()
    tx = LedgerClient(net).query_tx(tx_hash)
    if not tx.is_successful():
        return False
    candidates = [tx.events.get("transfer", {})] + [lg.events.get("transfer", {}) for lg in tx.logs]
    return any(_transfer_matches(c, recipient, min_amount) for c in candidates if c)


async def verify_fet_payment(tx_hash: str, recipient: str, amount_fet: str) -> bool:
    min_amount = to_base_units(amount_fet)
    try:
        return await _verify_via_rest(tx_hash, recipient, min_amount)
    except Exception as exc:  # noqa: BLE001
        log.warning("REST verification failed (%s); trying gRPC", exc)
    try:
        return await asyncio.to_thread(_verify_via_grpc, tx_hash, recipient, min_amount)
    except Exception as exc:  # noqa: BLE001
        log.error("gRPC verification failed: %s", exc)
        return False


@payment_proto.on_message(CommitPayment)
async def handle_commit(ctx: Context, sender: str, msg: CommitPayment):
    pending = ctx.storage.get(f"payref:{msg.reference}")
    if not pending or pending.get("user") != sender:
        ctx.logger.warning(f"CommitPayment with unknown reference {msg.reference}")
        await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id,
                                              reason="Unknown or expired payment reference"))
        return
    if pending.get("paid"):
        ctx.logger.info("Duplicate CommitPayment ignored")
        return

    ok = (
        msg.funds.payment_method == "fet_direct"
        and msg.funds.currency == "FET"
        and await verify_fet_payment(msg.transaction_id, recipient_wallet(ctx), config.PACK_PRICE_FET)
    )
    if not ok:
        await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id,
                                              reason="Payment could not be verified on-chain"))
        if on_declined:
            await on_declined(ctx, sender, pending, "verification_failed")
        return

    pending["paid"] = True
    pending["tx"] = msg.transaction_id
    ctx.storage.set(f"payref:{msg.reference}", pending)
    await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))
    if on_paid:
        await on_paid(ctx, sender, pending)


@payment_proto.on_message(RejectPayment)
async def handle_reject(ctx: Context, sender: str, msg: RejectPayment):
    ctx.logger.info(f"User declined payment: {msg.reason}")
    if on_declined:
        await on_declined(ctx, sender, {}, "rejected")
