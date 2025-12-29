from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_externalbankaccount'),
        ('banks', '0002_alter_bank_options_bank_code_bank_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='externalbankaccount',
            name='bank',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='banks.bank', null=True, blank=True),
        ),
        migrations.RemoveField(
            model_name='externalbankaccount',
            name='bank_name',
        ),
    ]
