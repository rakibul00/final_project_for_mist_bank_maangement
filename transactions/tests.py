from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.test import Client
from accounts.models import UserBankAccount
from banks.models import Bank
from transactions.models import Transaction
from transactions.forms import TransferForm
from transactions.constants import TRANSFER
from decimal import Decimal

class TransferFormTest(TestCase):
    def setUp(self):
        self.bank = Bank.objects.create(name='Test Bank')
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')
        self.account1 = UserBankAccount.objects.create(user=self.user1, account_no=1001, balance=1000, bank=self.bank)
        self.account2 = UserBankAccount.objects.create(user=self.user2, account_no=1002, balance=500, bank=self.bank)

    def test_form_valid(self):
        form = TransferForm(data={'recipient': self.account2.id, 'amount': 100}, account=self.account1)
        self.assertTrue(form.is_valid())

    def test_form_invalid_amount_zero(self):
        form = TransferForm(data={'recipient': self.account2.id, 'amount': 0}, account=self.account1)
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_form_invalid_insufficient_balance(self):
        form = TransferForm(data={'recipient': self.account2.id, 'amount': 2000}, account=self.account1)
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_form_recipient_queryset_excludes_sender(self):
        form = TransferForm(account=self.account1)
        self.assertNotIn(self.account1, form.fields['recipient'].queryset)
        self.assertIn(self.account2, form.fields['recipient'].queryset)


class TransferMoneyViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.bank = Bank.objects.create(name='Test Bank')
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')
        self.account1 = UserBankAccount.objects.create(user=self.user1, account_no=1001, balance=1000, bank=self.bank)
        self.account2 = UserBankAccount.objects.create(user=self.user2, account_no=1002, balance=500, bank=self.bank)

    def test_get_transfer_page(self):
        self.client.login(username='user1', password='pass')
        response = self.client.get(reverse('transfer_money'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'transactions/transfer.html')

    def test_post_transfer_success(self):
        self.client.login(username='user1', password='pass')
        data = {'recipient': self.account2.id, 'amount': 100}
        response = self.client.post(reverse('transfer_money'), data)
        self.assertRedirects(response, reverse('transaction_report'))
        self.account1.refresh_from_db()
        self.account2.refresh_from_db()
        self.assertEqual(self.account1.balance, Decimal('900'))
        self.assertEqual(self.account2.balance, Decimal('600'))
        # Check transactions created
        sender_transaction = Transaction.objects.get(account=self.account1, transaction_type=TRANSFER)
        receiver_transaction = Transaction.objects.get(account=self.account2, transaction_type=TRANSFER)
        self.assertFalse(sender_transaction.is_incoming)
        self.assertTrue(receiver_transaction.is_incoming)
