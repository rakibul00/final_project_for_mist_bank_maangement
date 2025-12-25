from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Branch(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    address = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')

    def __str__(self):
        return f"{self.name} ({self.code})"

class BranchChangeRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='branch_change_requests')
    current_branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='current_requests', null=True, blank=True)
    requested_branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='requested_requests')
    request_message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    admin_comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Request by {self.user.username} from {self.current_branch} to {self.requested_branch} - {self.status}"

    def approve(self):
        """Approve the request - branch update handled by signal"""
        self.status = 'Approved'
        self.save()

    def reject(self, comment):
        """Reject the request with admin comment"""
        self.status = 'Rejected'
        self.admin_comment = comment
        self.save()


@receiver(post_save, sender=BranchChangeRequest)
def handle_branch_change_request_status_change(sender, instance, created, **kwargs):
    """Automatically update user branch when request is approved"""
    if not created and instance.status == 'Approved':
        # Only update if this is a status change to Approved
        try:
            account = instance.user.account
            account.branch = instance.requested_branch
            account.save()
        except Exception as e:
            # Log the error but don't break the save
            print(f"Error updating branch for request {instance.id}: {e}")
            pass
