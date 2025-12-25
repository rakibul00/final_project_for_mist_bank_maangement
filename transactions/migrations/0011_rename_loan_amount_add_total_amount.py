from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0010_alter_loan_options_alter_transaction_options_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="loan",
            old_name="loan_amount",
            new_name="amount",
        ),
        migrations.AddField(
            model_name="loan",
            name="total_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14),
        ),
    ]
