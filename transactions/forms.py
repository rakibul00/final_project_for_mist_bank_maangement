from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import Transaction, Loan, LoanPayment
from accounts.models import UserBankAccount


class LoanApplyForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ('amount', 'loan_purpose')
        widgets = {
            'loan_purpose': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_amount(self):
        amt = self.cleaned_data.get('amount')
        if amt is None or amt <= Decimal('0'):
            raise forms.ValidationError('Loan amount must be greater than zero.')
        if amt < Decimal('500'):
            raise forms.ValidationError('Minimum loan amount is 500 BDT.')
        return amt


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['amount', 'note']

    def __init__(self, *args, **kwargs):
        self.account = kwargs.pop('account', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        # bind account/bank and set a snapshot balance_after_transaction
        instance = super().save(commit=False)
        if self.account:
            instance.account = self.account
            if hasattr(self.account, 'bank') and self.account.bank:
                instance.bank = self.account.bank
            # do not mutate account balance here; leave to caller or admin
            instance.balance_after_transaction = self.account.balance
        if commit:
            instance.save()
        return instance


class DepositForm(TransactionForm):
    def clean_amount(self):
        min_deposit_amount = Decimal('100')
        amount = self.cleaned_data.get('amount')
        if amount < min_deposit_amount:
            raise forms.ValidationError(f'You need to deposit at least {min_deposit_amount} $')
        return amount


class WithdrawForm(TransactionForm):
    def clean_amount(self):
        account = self.account
        min_withdraw_amount = Decimal('500')
        max_withdraw_amount = Decimal('200000000')
        balance = account.balance if account else Decimal('0')
        amount = self.cleaned_data.get('amount')
        if amount < min_withdraw_amount:
            raise forms.ValidationError(f'You can withdraw at least {min_withdraw_amount} $')
        if amount > max_withdraw_amount:
            raise forms.ValidationError(f'You can withdraw at most {max_withdraw_amount} $')
        if amount > balance:
            raise forms.ValidationError(f'You have {balance} $ in your account. You can not withdraw more than your account balance')
        return amount


class LoanRequestForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['amount', 'loan_purpose']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter loan amount',
                'min': '500',
                'step': '100'
            }),
            'loan_purpose': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe the purpose of the loan',
                'rows': 3
            })
        }
        labels = {
            'amount': 'Loan Amount',
            'loan_purpose': 'Loan Purpose'
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount < Decimal('500'):
            raise ValidationError('Minimum loan amount is 500 BDT')
        return amount


class TransferForm(TransactionForm):
    recipient = forms.ModelChoiceField(
        queryset=UserBankAccount.objects.none(),
        label='Recipient',
        empty_label='Select recipient',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'account') and self.account is not None:
            self.fields['recipient'].queryset = UserBankAccount.objects.exclude(id=self.account.id)

    def clean_amount(self):
        account = self.account
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise ValidationError('Transfer amount must be greater than zero')
        if account and amount > account.balance:
            raise ValidationError(f'You have {account.balance} $ in your account. You cannot transfer more than your balance')
        return amount


class LoanPaymentForm(forms.ModelForm):
    class Meta:
        model = LoanPayment
        fields = ['amount', 'payment_date']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter payment amount', 'min': '0', 'step': '0.01'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
        }
        labels = {'amount': 'Payment Amount ($)', 'payment_date': 'Payment Date'}

    def __init__(self, *args, **kwargs):
        self.loan = kwargs.pop('loan', None)
        self.account = kwargs.pop('account', None)
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if self.loan:
            total_payable = self.loan.total_amount
            if amount != total_payable:
                raise ValidationError(f'You must pay the full amount of {total_payable} (loan + interest)')
        return amount

    def clean(self):
        cleaned_data = super().clean()
        if self.account and self.loan:
            amount = cleaned_data.get('amount')
            if amount and amount > self.account.balance:
                raise ValidationError('Insufficient balance to make this payment')
        return cleaned_data