"""Unit tests for the in-memory AccountStore domain logic."""

from decimal import Decimal

import pytest

from financial_account_store import (
    AccountAlreadyExistsError,
    AccountStore,
    InsufficientFundsError,
    InvalidAmountError,
    UnknownAccountError,
)


def test_open_account_starts_at_zero():
    store = AccountStore()
    account = store.open_account("alice")
    assert account.account_id == "alice"
    assert account.balance == Decimal("0")
    assert store.get_balance("alice") == Decimal("0")


def test_open_duplicate_account_raises():
    store = AccountStore()
    store.open_account("alice")
    with pytest.raises(AccountAlreadyExistsError):
        store.open_account("alice")


def test_get_balance_unknown_account_raises():
    store = AccountStore()
    with pytest.raises(UnknownAccountError):
        store.get_balance("ghost")


def test_deposit_increases_balance():
    store = AccountStore()
    store.open_account("alice")
    txn = store.deposit("alice", "100.50")
    assert txn.kind == "deposit"
    assert txn.amount == Decimal("100.50")
    assert store.get_balance("alice") == Decimal("100.50")


def test_withdraw_decreases_balance():
    store = AccountStore()
    store.open_account("alice")
    store.deposit("alice", "100")
    store.withdraw("alice", "40")
    assert store.get_balance("alice") == Decimal("60")


def test_withdraw_more_than_balance_raises():
    store = AccountStore()
    store.open_account("alice")
    store.deposit("alice", "30")
    with pytest.raises(InsufficientFundsError):
        store.withdraw("alice", "31")
    # balance unchanged after a failed withdrawal
    assert store.get_balance("alice") == Decimal("30")


def test_transfer_moves_funds_between_accounts():
    store = AccountStore()
    store.open_account("alice")
    store.open_account("bob")
    store.deposit("alice", "100")
    txn = store.transfer("alice", "bob", "25")
    assert txn.kind == "transfer"
    assert txn.account_id == "alice"
    assert txn.counterparty == "bob"
    assert store.get_balance("alice") == Decimal("75")
    assert store.get_balance("bob") == Decimal("25")


def test_transfer_insufficient_funds_is_atomic():
    store = AccountStore()
    store.open_account("alice")
    store.open_account("bob")
    store.deposit("alice", "10")
    with pytest.raises(InsufficientFundsError):
        store.transfer("alice", "bob", "50")
    # neither balance changed
    assert store.get_balance("alice") == Decimal("10")
    assert store.get_balance("bob") == Decimal("0")


def test_transfer_unknown_destination_raises():
    store = AccountStore()
    store.open_account("alice")
    store.deposit("alice", "10")
    with pytest.raises(UnknownAccountError):
        store.transfer("alice", "ghost", "5")
    assert store.get_balance("alice") == Decimal("10")


@pytest.mark.parametrize("bad", ["0", "-5", "abc", ""])
def test_deposit_invalid_amount_raises(bad):
    store = AccountStore()
    store.open_account("alice")
    with pytest.raises(InvalidAmountError):
        store.deposit("alice", bad)


def test_list_transactions_records_history():
    store = AccountStore()
    store.open_account("alice")
    store.open_account("bob")
    store.deposit("alice", "100")
    store.withdraw("alice", "10")
    store.transfer("alice", "bob", "20")

    all_txns = store.list_transactions()
    assert [t.kind for t in all_txns] == ["deposit", "withdraw", "transfer"]
    assert [t.id for t in all_txns] == [1, 2, 3]

    # bob only appears as the transfer counterparty
    bob_txns = store.list_transactions("bob")
    assert len(bob_txns) == 1
    assert bob_txns[0].kind == "transfer"
