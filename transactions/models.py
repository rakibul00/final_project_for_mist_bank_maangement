from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal
from accounts.models import UserBankAccount
from banks.models import Bank


class Transaction(models.Model):
    """Lightweight transaction record used across the project."""
    account = models.ForeignKey(UserBankAccount, related_name='transactions', on_delete=models.CASCADE)
    bank = models.ForeignKey(Bank, related_name='transactions', on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    transaction_type = models.IntegerField(choices=[(1, 'Deposite'), (2, 'Withdrawal'), (3, 'Loan'), (4, 'Loan Paid'), (5, 'Transfer')], null=True, blank=True)
    is_incoming = models.BooleanField(default=False)
    balance_after_transaction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Transaction {self.id} - {self.account} - {self.amount}"


class Loan(models.Model):
    """Loan application and lifecycle model.

    - `user` is a `UserBankAccount` (profile) that contains the `balance` field.
    - `interest_rate` stored as Decimal (default 0.08 for 8%).
    - `status` transitions: PENDING -> APPROVED/REJECTED -> PAID
    """

    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_PAID = 'PAID'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_PAID, 'Paid'),
    ]

    user = models.ForeignKey(UserBankAccount, on_delete=models.CASCADE, related_name='loans')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.08'))
    duration_months = models.PositiveIntegerField(default=12)
    loan_purpose = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    applied_date = models.DateField(default=timezone.now)
    approved_date = models.DateTimeField(null=True, blank=True)
    paid_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-applied_date']

    def __str__(self):
        return f'Loan {self.id} - {self.user.user.username} - {self.amount} ({self.status})'

    def save(self, *args, **kwargs):
        from django.db import transaction
        # compute total_amount = amount + (amount * interest_rate)
        if self.amount is not None:
            self.total_amount = (self.amount + (self.amount * self.interest_rate)).quantize(Decimal('0.01'))
        
        # Check if status is changing to APPROVED
        if self.pk:  # existing loan
            old_loan = Loan.objects.get(pk=self.pk)
            if old_loan.status != self.STATUS_APPROVED and self.status == self.STATUS_APPROVED:
                # Status changed to APPROVED, add to balance
                with transaction.atomic():
                    account = self.user
                    account.refresh_from_db()
                    account.balance += self.amount
                    account.save()
                    
                    # Create transaction record
                    Transaction.objects.create(
                        account=account,
                        amount=self.amount,
                        balance_after_transaction=account.balance,
                        transaction_type=3,  # Loan
                        note=f'Loan disbursement for Loan {self.id}'
                    )
                    self.approved_date = timezone.now()
        elif self.status == self.STATUS_APPROVED:
            # New loan directly approved
            with transaction.atomic():
                account = self.user
                account.refresh_from_db()
                account.balance += self.amount
                account.save()
                
                Transaction.objects.create(
                    account=account,
                    amount=self.amount,
                    balance_after_transaction=account.balance,
                    transaction_type=3,  # Loan
                    note=f'Loan disbursement for Loan {self.id}'
                )
                self.approved_date = timezone.now()
        
        super().save(*args, **kwargs)

    @property
    def interest_amount(self):
        """Return computed interest amount (total - principal)."""
        return (self.total_amount - self.amount).quantize(Decimal('0.01'))


class LoanPayment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    payer = models.ForeignKey(UserBankAccount, on_delete=models.CASCADE, related_name='loan_payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'Payment {self.id} for Loan {self.loan.id} - {self.amount}'

    def save(self, *args, **kwargs):
        # ensure Decimal quantization
        if isinstance(self.amount, float):
            self.amount = Decimal(str(self.amount))
        self.amount = self.amount.quantize(Decimal('0.01'))
        super().save(*args, **kwargs)