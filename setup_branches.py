#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mamar_bank.settings')
django.setup()

from branch_management.models import Branch
from accounts.models import UserBankAccount

# Create some branches
branch1 = Branch.objects.create(name='Main Branch', code='MAIN', address='123 Main St, City')
branch2 = Branch.objects.create(name='Downtown Branch', code='DOWN', address='456 Downtown Ave, City')
branch3 = Branch.objects.create(name='Suburban Branch', code='SUB', address='789 Suburban Rd, City')

# Assign default branch to existing users
for account in UserBankAccount.objects.all():
    if not account.branch:
        account.branch = branch1
        account.save()

print('Branches created and assigned.')