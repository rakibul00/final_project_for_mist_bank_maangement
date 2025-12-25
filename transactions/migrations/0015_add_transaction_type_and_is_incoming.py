from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0014_alter_loan_options_remove_loan_created_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='transaction_type',
            field=models.IntegerField(choices=[(1, 'Deposite'), (2, 'Withdrawal'), (3, 'Loan'), (4, 'Loan Paid'), (5, 'Transfer')], null=True, blank=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='is_incoming',
            field=models.BooleanField(default=False),
        ),
    ]
