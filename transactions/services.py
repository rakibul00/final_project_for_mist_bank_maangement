from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from accounts.models import UserBankAccount, ExternalBankAccount
from transactions.models import Transaction
from transactions.constants import WITHDRAWAL, TRANSFER, EXTERNAL_WITHDRAWAL, EXTERNAL_TRANSFER


class InsufficientBalanceError(ValidationError):
    """Custom exception for insufficient balance errors with structured data."""

    def __init__(self, available_balance, requested_amount, account_type="account", account_name=""):
        self.available_balance = available_balance
        self.requested_amount = requested_amount
        self.account_type = account_type
        self.account_name = account_name

        # Create user-friendly message
        message = "Transaction failed due to insufficient balance."
        if account_name:
            message += f" {account_type.title()}: {account_name}"

        super().__init__(message)

    def get_context(self):
        """Return context data for template rendering."""
        return {
            'available_balance': self.available_balance,
            'requested_amount': self.requested_amount,
            'account_type': self.account_type,
            'account_name': self.account_name,
            'shortage_amount': self.requested_amount - self.available_balance
        }


class BalanceService:
    """Service layer for handling all balance-related operations with proper validation and atomicity."""

    @staticmethod
    @transaction.atomic
    def withdraw_from_main_account(user_account, amount, note=None):
        """
        Withdraw money from main account with proper validation and atomicity.

        Args:
            user_account: UserBankAccount instance
            amount: Decimal amount to withdraw
            note: Optional note for transaction

        Returns:
            Transaction: Created transaction record

        Raises:
            InsufficientBalanceError: If balance is insufficient
        """
        if amount <= 0:
            raise ValidationError("Withdrawal amount must be greater than zero")

        # Lock the account row to prevent concurrent modifications
        account = UserBankAccount.objects.select_for_update().get(pk=user_account.pk)

        if account.balance < amount:
            raise InsufficientBalanceError(
                available_balance=account.balance,
                requested_amount=amount,
                account_type="main account",
                account_name=f"Account #{account.account_no}"
            )

        # Deduct balance
        account.balance -= amount
        account.save(update_fields=['balance'])

        # Create transaction record
        transaction_record = Transaction.objects.create(
            account=account,
            amount=-amount,
            balance_after_transaction=account.balance,
            transaction_type=WITHDRAWAL,
            note=note or f'Withdrawal of ${amount}'
        )

        return transaction_record

    @staticmethod
    @transaction.atomic
    def withdraw_from_external_account(user, external_account, amount, note=None):
        """
        Withdraw money from external account with proper validation and atomicity.

        Args:
            user: User instance (for ownership validation)
            external_account: ExternalBankAccount instance
            amount: Decimal amount to withdraw
            note: Optional note for transaction

        Returns:
            Transaction: Created transaction record

        Raises:
            InsufficientBalanceError: If balance is insufficient or ownership issues
        """
        if amount <= 0:
            raise ValidationError("Withdrawal amount must be greater than zero")

        # Validate ownership
        if external_account.user != user:
            raise ValidationError("You do not have permission to access this external account")

        # Lock the external account row
        ext_account = ExternalBankAccount.objects.select_for_update().get(pk=external_account.pk)

        if ext_account.current_balance < amount:
            raise InsufficientBalanceError(
                available_balance=ext_account.current_balance,
                requested_amount=amount,
                account_type="external account",
                account_name=f"{ext_account.bank.name if ext_account.bank else 'Unknown Bank'} - {ext_account.account_number}"
            )

        # Deduct balance
        ext_account.current_balance -= amount
        ext_account.save(update_fields=['current_balance'])

        # Create transaction record
        transaction_record = Transaction.objects.create(
            account=user.account,
            external_account=ext_account,
            amount=-amount,
            balance_after_transaction=user.account.balance,  # Main account unchanged
            external_balance_after_transaction=ext_account.current_balance,
            transaction_type=EXTERNAL_WITHDRAWAL,
            note=note or f'Withdrawal from external account {ext_account.account_number}'
        )

        return transaction_record

    @staticmethod
    @transaction.atomic
    def transfer_from_main_account(sender_account, recipient_account, amount, note=None):
        """
        Transfer money from main account to another main account.

        Args:
            sender_account: UserBankAccount instance (sender)
            recipient_account: UserBankAccount instance (recipient)
            amount: Decimal amount to transfer
            note: Optional note for transaction

        Returns:
            tuple: (sender_transaction, recipient_transaction)

        Raises:
            InsufficientBalanceError: If balance is insufficient
        """
        if amount <= 0:
            raise ValidationError("Transfer amount must be greater than zero")

        if sender_account == recipient_account:
            raise ValidationError("Cannot transfer to the same account")

        # Lock both account rows to prevent deadlocks (lock in consistent order)
        accounts = UserBankAccount.objects.select_for_update().filter(
            pk__in=[sender_account.pk, recipient_account.pk]
        ).order_by('pk')

        sender = accounts[0] if accounts[0].pk == sender_account.pk else accounts[1]
        recipient = accounts[1] if accounts[1].pk == recipient_account.pk else accounts[0]

        if sender.balance < amount:
            raise InsufficientBalanceError(
                available_balance=sender.balance,
                requested_amount=amount,
                account_type="main account",
                account_name=f"Account #{sender.account_no}"
            )

        # Perform transfer
        sender.balance -= amount
        recipient.balance += amount

        sender.save(update_fields=['balance'])
        recipient.save(update_fields=['balance'])

        # Create transaction records
        sender_transaction = Transaction.objects.create(
            account=sender,
            amount=-amount,
            balance_after_transaction=sender.balance,
            transaction_type=TRANSFER,
            is_incoming=False,
            note=note or f'Transfer to {recipient.user.username}'
        )

        recipient_transaction = Transaction.objects.create(
            account=recipient,
            amount=amount,
            balance_after_transaction=recipient.balance,
            transaction_type=TRANSFER,
            is_incoming=True,
            note=note or f'Transfer from {sender.user.username}'
        )

        return sender_transaction, recipient_transaction

    @staticmethod
    @transaction.atomic
    def transfer_from_external_account(user, external_account, recipient_account, amount, note=None):
        """
        Transfer money from external account to another main account.

        Args:
            user: User instance (for ownership validation)
            external_account: ExternalBankAccount instance
            recipient_account: UserBankAccount instance (recipient)
            amount: Decimal amount to transfer
            note: Optional note for transaction

        Returns:
            tuple: (sender_transaction, recipient_transaction)

        Raises:
            ValidationError: If balance is insufficient or ownership issues
        """
        if amount <= 0:
            raise ValidationError("Transfer amount must be greater than zero")

        # Validate ownership
        if external_account.user != user:
            raise ValidationError("You do not have permission to access this external account")

        # Lock both account rows
        ext_account = ExternalBankAccount.objects.select_for_update().get(pk=external_account.pk)
        recipient = UserBankAccount.objects.select_for_update().get(pk=recipient_account.pk)

        if ext_account.current_balance < amount:
            raise InsufficientBalanceError(
                available_balance=ext_account.current_balance,
                requested_amount=amount,
                account_type="external account",
                account_name=f"{ext_account.bank.name if ext_account.bank else 'Unknown Bank'} - {ext_account.account_number}"
            )

        # Perform transfer
        ext_account.current_balance -= amount
        recipient.balance += amount

        ext_account.save(update_fields=['current_balance'])
        recipient.save(update_fields=['balance'])

        # Create transaction records
        sender_transaction = Transaction.objects.create(
            account=user.account,
            external_account=ext_account,
            amount=-amount,
            balance_after_transaction=user.account.balance,  # Main account unchanged
            external_balance_after_transaction=ext_account.current_balance,
            transaction_type=EXTERNAL_TRANSFER,
            note=note or f'Transfer from external account to {recipient.user.username}'
        )

        recipient_transaction = Transaction.objects.create(
            account=recipient,
            amount=amount,
            balance_after_transaction=recipient.balance,
            transaction_type=TRANSFER,
            is_incoming=True,
            note=note or f'Transfer from {user.username} (external account)'
        )

        return sender_transaction, recipient_transaction

    @staticmethod
    def validate_sufficient_balance(account, amount):
        """
        Validate if account has sufficient balance for the operation.

        Args:
            account: UserBankAccount instance
            amount: Decimal amount needed

        Returns:
            bool: True if sufficient balance

        Raises:
            ValidationError: If insufficient balance
        """
        if account.balance < amount:
            raise ValidationError(
                f"Insufficient balance. Your account has ${account.balance} but needs ${amount}"
            )
        return True

    @staticmethod
    def validate_external_balance(external_account, amount):
        """
        Validate if external account has sufficient balance.

        Args:
            external_account: ExternalBankAccount instance
            amount: Decimal amount needed

        Returns:
            bool: True if sufficient balance

        Raises:
            ValidationError: If insufficient balance
        """
        if external_account.current_balance < amount:
            raise ValidationError(
                f"Insufficient balance. External account has ${external_account.current_balance} but needs ${amount}"
            )
        return True