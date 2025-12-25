from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0011_rename_loan_amount_add_total_amount"),
    ]

    operations = [
        migrations.AddField(
            model_name='loan',
            name='paid_date',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
