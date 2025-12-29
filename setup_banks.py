#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mamar_bank.settings')
django.setup()

from banks.models import Bank

# Create the predefined banks
banks_data = [
    {'name': 'Islamic Bank', 'code': 'IBBL'},
    {'name': 'Sonali Bank', 'code': 'SONALI'},
    {'name': 'Pubali Bank', 'code': 'PUBALI'},
    {'name': 'Uttara Bank', 'code': 'UTTARA'},
]

for bank_data in banks_data:
    bank, created = Bank.objects.get_or_create(
        name=bank_data['name'],
        defaults={'code': bank_data['code'], 'is_active': True}
    )
    if created:
        print(f'Created bank: {bank}')
    else:
        print(f'Bank already exists: {bank}')

print('Bank setup completed.')