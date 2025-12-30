from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal
from accounts.models import UserBankAccount, ExternalBankAccount, Bank
from transactions.models import Transaction
from transactions.services import BalanceService


class BalanceValidationTestCase(TestCase):
    """Test cases for balance validation and negative balance prevention"""

    def setUp(self):
        """Set up test data"""
        # Create test bank
        self.bank = Bank.objects.create(
            name='Test Bank',
            code='TEST',
            is_active=True
        )

        # Create test users
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )

        # Create user accounts
        self.account1 = UserBankAccount.objects.create(
            user=self.user1,
            bank=self.bank,
            account_type='Savings',
            gender='Male',
            account_no=10001,
            balance=Decimal('1000.00')
        )
        self.account2 = UserBankAccount.objects.create(
            user=self.user2,
            bank=self.bank,
            account_type='Savings',
            gender='Female',
            account_no=10002,
            balance=Decimal('500.00')
        )

        # Create external account
        self.external_account = ExternalBankAccount.objects.create(
            user=self.user1,
            account_holder_name='Test User',
            account_number='EXT123456',
            bank=self.bank,
            current_balance=Decimal('2000.00')
        )

    def test_withdraw_exact_balance_success(self):
        """Test withdrawing exact balance amount - should succeed"""
        initial_balance = self.account1.balance

        transaction_record = BalanceService.withdraw_from_main_account(
            user_account=self.account1,
            amount=Decimal('1000.00'),
            note='Test withdrawal'
        )

        self.account1.refresh_from_db()
        self.assertEqual(self.account1.balance, Decimal('0.00'))
        self.assertEqual(transaction_record.amount, Decimal('-1000.00'))
        self.assertEqual(transaction_record.balance_after_transaction, Decimal('0.00'))

    def test_withdraw_less_than_balance_success(self):
        """Test withdrawing less than balance - should succeed"""
        initial_balance = self.account1.balance

        transaction_record = BalanceService.withdraw_from_main_account(
            user_account=self.account1,
            amount=Decimal('500.00'),
            note='Test withdrawal'
        )

        self.account1.refresh_from_db()
        self.assertEqual(self.account1.balance, Decimal('500.00'))
        self.assertEqual(transaction_record.amount, Decimal('-500.00'))

    def test_withdraw_more_than_balance_fails(self):
        """Test withdrawing more than balance - should fail"""
        with self.assertRaises(ValidationError) as cm:
            BalanceService.withdraw_from_main_account(
                user_account=self.account1,
                amount=Decimal('1500.00'),  # More than 1000
                note='Test withdrawal'
            )

        self.assertIn('Insufficient balance', str(cm.exception))
        # Balance should remain unchanged
        self.account1.refresh_from_db()
        self.assertEqual(self.account1.balance, Decimal('1000.00'))

    def test_external_withdraw_exact_balance_success(self):
        """Test external account withdrawal with exact balance"""
        transaction_record = BalanceService.withdraw_from_external_account(
            user=self.user1,
            external_account=self.external_account,
            amount=Decimal('2000.00'),
            note='Test external withdrawal'
        )

        self.external_account.refresh_from_db()
        self.assertEqual(self.external_account.current_balance, Decimal('0.00'))
        self.assertEqual(transaction_record.amount, Decimal('-2000.00'))

    def test_external_withdraw_more_than_balance_fails(self):
        """Test external account withdrawal with insufficient balance"""
        with self.assertRaises(ValidationError) as cm:
            BalanceService.withdraw_from_external_account(
                user=self.user1,
                external_account=self.external_account,
                amount=Decimal('2500.00'),  # More than 2000
                note='Test external withdrawal'
            )

        self.assertIn('Insufficient balance', str(cm.exception))
        # Balance should remain unchanged
        self.external_account.refresh_from_db()
        self.assertEqual(self.external_account.current_balance, Decimal('2000.00'))

    def test_transfer_success(self):
        """Test successful transfer between accounts"""
        initial_sender_balance = self.account1.balance
        initial_recipient_balance = self.account2.balance

        sender_tx, recipient_tx = BalanceService.transfer_from_main_account(
            sender_account=self.account1,
            recipient_account=self.account2,
            amount=Decimal('300.00'),
            note='Test transfer'
        )

        self.account1.refresh_from_db()
        self.account2.refresh_from_db()

        self.assertEqual(self.account1.balance, initial_sender_balance - Decimal('300.00'))
        self.assertEqual(self.account2.balance, initial_recipient_balance + Decimal('300.00'))
        self.assertEqual(sender_tx.amount, Decimal('-300.00'))
        self.assertEqual(recipient_tx.amount, Decimal('300.00'))

    def test_transfer_insufficient_balance_fails(self):
        """Test transfer with insufficient balance fails"""
        with self.assertRaises(ValidationError) as cm:
            BalanceService.transfer_from_main_account(
                sender_account=self.account1,
                recipient_account=self.account2,
                amount=Decimal('1500.00'),  # More than sender's 1000
                note='Test transfer'
            )

        self.assertIn('Insufficient balance', str(cm.exception))
        # Balances should remain unchanged
        self.account1.refresh_from_db()
        self.account2.refresh_from_db()
        self.assertEqual(self.account1.balance, Decimal('1000.00'))
        self.assertEqual(self.account2.balance, Decimal('500.00'))

    def test_concurrent_transactions_prevent_negative_balance(self):
        """Test that concurrent transactions don't create negative balances"""
        from django.db import connection
        from django.test.utils import override_settings
        import threading
        import time

        results = []

        def withdraw_transaction(amount, result_list):
            try:
                with transaction.atomic():
                    BalanceService.withdraw_from_main_account(
                        user_account=self.account1,
                        amount=amount,
                        note=f'Concurrent withdrawal {amount}'
                    )
                result_list.append('success')
            except ValidationError:
                result_list.append('failed')

        # Start multiple concurrent withdrawals
        threads = []
        for i in range(3):
            t = threading.Thread(target=withdraw_transaction, args=(Decimal('400.00'), results))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Only one should succeed (total balance is 1000, each withdrawal is 400)
        success_count = results.count('success')
        fail_count = results.count('failed')

        self.assertEqual(success_count, 1)  # Only one should succeed
        self.assertEqual(fail_count, 2)     # Two should fail

        # Final balance should be either 600 (if one succeeded) or 1000 (if all failed)
        self.account1.refresh_from_db()
        self.assertTrue(self.account1.balance >= 0)  # Never negative
        self.assertIn(self.account1.balance, [Decimal('600.00'), Decimal('1000.00')])

    def test_model_validation_prevents_negative_balance(self):
        """Test that model-level validation prevents negative balances"""
        # Try to set negative balance directly
        self.account1.balance = Decimal('-100.00')
        with self.assertRaises(ValidationError) as cm:
            self.account1.save()

        self.assertIn('cannot be negative', str(cm.exception))

        # Try to set negative external balance
        self.external_account.current_balance = Decimal('-50.00')
        with self.assertRaises(ValidationError) as cm:
            self.external_account.save()

        self.assertIn('cannot be negative', str(cm.exception))