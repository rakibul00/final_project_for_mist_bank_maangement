from django.contrib import admin
from .models import UserBankAccount, UserAddress, AccountClosureRequest
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

from django.contrib import admin
from .models import UserBankAccount, UserAddress, AccountClosureRequest
# Register your models here.

@admin.register(UserBankAccount)
class UserBankAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'bank', 'branch', 'account_type', 'role', 'account_no', 'balance', 'is_active']
    list_filter = ['bank', 'branch', 'account_type', 'role', 'is_active']
    search_fields = ['user__username', 'account_no']

admin.site.register(UserAddress)