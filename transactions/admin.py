from django.contrib import admin
from django.utils import timezone
from django.contrib.admin import ModelAdmin

from .models import Loan, LoanPayment, Transaction


@admin.register(Loan)
class LoanAdmin(ModelAdmin):
    list_display = ('id', 'user', 'amount', 'interest_rate', 'total_amount', 'status', 'applied_date', 'approved_date', 'paid_date')
    list_filter = ('status', 'applied_date', 'approved_date', 'paid_date')
    search_fields = ('user__user__username', 'amount')
    readonly_fields = ('applied_date', 'approved_date', 'paid_date', 'total_amount')
    actions = ['approve_loans', 'reject_loans']

    def approve_loans(self, request, queryset):
        approved_count = 0
        for loan in queryset.filter(status=Loan.STATUS_PENDING):
            loan.status = Loan.STATUS_APPROVED
            loan.save()  # This will trigger the balance update in the model's save method
            approved_count += 1
        self.message_user(request, f'Successfully approved {approved_count} loan(s).')

    def reject_loans(self, request, queryset):
        rejected_count = 0
        for loan in queryset.filter(status=Loan.STATUS_PENDING):
            loan.status = Loan.STATUS_REJECTED
            loan.save()
            rejected_count += 1
        self.message_user(request, f'Successfully rejected {rejected_count} loan(s).')

    approve_loans.short_description = "Approve selected loans"
    reject_loans.short_description = "Reject selected loans"


@admin.register(LoanPayment)
class LoanPaymentAdmin(ModelAdmin):
    list_display = ('loan', 'payer', 'amount', 'payment_date')
    search_fields = ('loan__id', 'payer__user__username')

