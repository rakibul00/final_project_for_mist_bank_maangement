from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from django.core.exceptions import ValidationError
from .constants import ACCOUNT_TYPE, GENDER_TYPE
from banks.models import Bank
from branch_management.models import Branch
# django amaderke built in user niye kaj korar facility dey


class UserBankAccount(models.Model):
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Staff', 'Staff'),
        ('Customer', 'Customer'),
    ]

    user = models.OneToOneField(User, related_name='account', on_delete=models.CASCADE)
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='accounts')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='accounts', null=True, blank=True)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='Customer')
    account_no = models.IntegerField(unique=True) # account no duijon user er kokhono same hobe na
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_TYPE)
    initial_deposite_date = models.DateField(auto_now_add=True)
    balance = models.DecimalField(default=0, max_digits=12, decimal_places=2) # ekjon user 12 digit obdi taka rakhte parbe, dui doshomik ghor obdi rakhte parben 1000.50
    
    def clean(self):
        """Model-level validation to prevent negative balance"""
        if self.balance < 0:
            raise ValidationError({'balance': 'Account balance cannot be negative'})
    
    def save(self, *args, **kwargs):
        self.clean()  # Validate before saving
        super().save(*args, **kwargs)
    is_active = models.BooleanField(default=True)
    
    @property
    def total_balance(self):
        """Calculate total balance including external bank accounts"""
        from decimal import Decimal
        external_balance = self.user.external_accounts.aggregate(
            total=models.Sum('current_balance')
        )['total'] or Decimal('0')
        return self.balance + external_balance
    
    @property
    def external_accounts_balance(self):
        """Get total balance from external accounts only"""
        from decimal import Decimal
        return self.user.external_accounts.aggregate(
            total=models.Sum('current_balance')
        )['total'] or Decimal('0')
    
    def __str__(self):
        return f"{self.bank.name} - {self.account_no}"
    
class AccountClosure(models.Model):
    account = models.ForeignKey(UserBankAccount, on_delete=models.CASCADE, related_name='closures')
    reason = models.CharField(max_length=300)
    closed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Closure for {self.account} on {self.closed_at}"
    
class AccountClosureRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='closure_requests')
    reason = models.CharField(max_length=300)
    is_approved = models.BooleanField(default=False)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Closure request by {self.user.username} - {'Approved' if self.is_approved else 'Pending'}"

    def approve(self):
        """Approve the closure request and close the account"""
        from django.utils import timezone
        from notifications.models import Notification
        self.is_approved = True
        self.approved_at = timezone.now()
        self.save()
        # Close the account if it exists
        try:
            account = self.user.account
            account.is_active = False
            account.save()
            # Create closure record
            AccountClosure.objects.create(account=account, reason=self.reason)
            # Notify the user
            Notification.objects.create(
                user=self.user,
                message="Your account closure request has been approved. Your account has been closed."
            )
        except UserBankAccount.DoesNotExist:
            # If no account, just mark as approved
            Notification.objects.create(
                user=self.user,
                message="Your account closure request has been approved. However, no active account was found."
            )
    
class UserAddress(models.Model):
    user = models.OneToOneField(User, related_name='address', on_delete=models.CASCADE)
    street_address = models.CharField(max_length=100)
    city = models.CharField(max_length= 100)
    postal_code = models.IntegerField()
    country = models.CharField(max_length=100)
    def __str__(self):
        return str(self.user.email)


class ExternalBankAccount(models.Model):
    """Model for storing external bank accounts linked to users"""

    user = models.ForeignKey(User, related_name='external_accounts', on_delete=models.CASCADE)
    account_holder_name = models.CharField(max_length=100, default='')
    account_number = models.CharField(max_length=50, unique=True)
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, null=True, blank=True)
    branch_name = models.CharField(max_length=100, default='')
    date_added = models.DateField(default='2025-01-01')
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Model-level validation to prevent negative balance"""
        if self.current_balance < 0:
            raise ValidationError({'current_balance': 'External account balance cannot be negative'})
    
    def save(self, *args, **kwargs):
        self.clean()  # Validate before saving
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-date_added']
        verbose_name = 'External Bank Account'
        verbose_name_plural = 'External Bank Accounts'
        constraints = [
            models.UniqueConstraint(fields=['user', 'bank'], name='unique_user_bank_external')
        ]

    def __str__(self):
        bank_name = self.bank.name if self.bank else 'Unknown Bank'
        return f"{bank_name} - {self.account_number} ({self.account_holder_name})"
    