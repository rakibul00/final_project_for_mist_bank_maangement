from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0012_add_paid_date"),
    ]

    operations = [
        migrations.RenameField(
            model_name='loanpayment',
            old_name='user',
            new_name='payer',
        ),
    ]
