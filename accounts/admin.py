from django.contrib import admin
from .models import UserBankAccount, UserAddress, AccountClosureRequest, ExternalBankAccount
# Register your models here.

@admin.register(AccountClosureRequest)
class AccountClosureRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'reason', 'is_approved', 'requested_at', 'approved_at']
    list_filter = ['is_approved', 'requested_at', 'approved_at']
    search_fields = ['user__username', 'reason']
    readonly_fields = ['requested_at']
    
    def save_model(self, request, obj, form, change):
        # Check if this is an approval (either new or update)
        if obj.is_approved and not obj.approved_at:
            obj.approve()
        super().save_model(request, obj, form, change)

@admin.register(UserBankAccount)
class UserBankAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'bank', 'branch', 'account_type', 'role', 'account_no', 'balance', 'is_active']
    list_filter = ['bank', 'branch', 'account_type', 'role', 'is_active']
    search_fields = ['user__username', 'account_no']

@admin.register(ExternalBankAccount)
class ExternalBankAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'account_holder_name', 'account_number', 'bank', 'branch_name', 'date_added', 'current_balance']
    list_filter = ['bank', 'date_added']
    search_fields = ['bank__name', 'account_number', 'account_holder_name']
    readonly_fields = ['created_at', 'updated_at']

admin.site.register(UserAddress)