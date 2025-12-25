from django.db.models.signals import post_save
from django.dispatch import receiver
from transactions.models import Transaction
from .models import Notification

@receiver(post_save, sender=Transaction)
def create_transaction_notification(sender, instance, created, **kwargs):
    if created:
        user = instance.account.user
        transaction_type = instance.get_transaction_type_display()
        amount = instance.amount

        if instance.transaction_type == 1:  # Deposit
            message = f"Deposit of ${amount} was successful"
        elif instance.transaction_type == 2:  # Withdrawal
            message = f"Withdrawal of ${amount} was successful"
        elif instance.transaction_type == 3:  # Loan
            message = f"Loan request for ${amount} submitted"
        elif instance.transaction_type == 4:  # Loan Paid
            message = f"Loan payment of ${amount} was successful"
        elif instance.transaction_type == 5:  # Transfer
            if instance.is_incoming:
                message = f"Received ${amount} via transfer"
            else:
                message = f"Transferred ${amount} successfully"
        else:
            message = f"Transaction of ${amount} completed"

        Notification.objects.create(
            user=user,
            message=message,
            transaction=instance
        )