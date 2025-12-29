from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_add_bank_field_and_remove_bank_name'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='externalbankaccount',
            constraint=models.UniqueConstraint(fields=['user', 'bank'], name='unique_user_bank_external'),
        ),
    ]
