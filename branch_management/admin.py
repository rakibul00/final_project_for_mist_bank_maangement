from django.contrib import admin
from .models import Branch, BranchChangeRequest

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'address', 'status')
    list_filter = ('status',)
    search_fields = ('name', 'code')

@admin.register(BranchChangeRequest)
class BranchChangeRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_branch', 'requested_branch', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'current_branch__name', 'requested_branch__name')
    readonly_fields = ('created_at',)
    actions = ['approve_requests', 'reject_requests']

    def has_add_permission(self, request):
        return False  # Requests should be created by users, not admins

    def has_delete_permission(self, request, obj=None):
        return False  # Prevent deletion of requests

    def approve_requests(self, request, queryset):
        """Approve selected branch change requests"""
        approved_count = 0
        for branch_request in queryset.filter(status='Pending'):
            branch_request.status = 'Approved'
            branch_request.save()
            approved_count += 1
        self.message_user(request, f'Successfully approved {approved_count} branch change requests.')

    def reject_requests(self, request, queryset):
        """Reject selected branch change requests"""
        rejected_count = 0
        for branch_request in queryset.filter(status='Pending'):
            branch_request.status = 'Rejected'
            branch_request.admin_comment = 'Rejected via bulk action'
            branch_request.save()
            rejected_count += 1
        self.message_user(request, f'Successfully rejected {rejected_count} branch change requests.')

    approve_requests.short_description = "Approve selected branch change requests"
    reject_requests.short_description = "Reject selected branch change requests"
