from django.contrib import admin
from .models import Bank
from accounts.models import UserBankAccount
from transactions.models import Transaction

class UserBankAccountInline(admin.TabularInline):
    model = UserBankAccount
    extra = 0
    readonly_fields = ('account_no', 'balance')

class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ('amount', 'balance_after_transaction', 'timestamp')
    can_delete = False

@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    inlines = [UserBankAccountInline, TransactionInline]
    list_display = ('name', 'code', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    ordering = ('name',)
