from django.urls import path
from . import views

app_name = 'banks'

urlpatterns = [
    path('', views.BankListView.as_view(), name='bank_list'),
]