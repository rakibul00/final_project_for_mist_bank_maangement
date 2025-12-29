from django.shortcuts import render
from django.views.generic import ListView
from .models import Bank

class BankListView(ListView):
    model = Bank
    template_name = 'banks/bank_list.html'
    context_object_name = 'banks'
    queryset = Bank.objects.filter(is_active=True).order_by('name')
