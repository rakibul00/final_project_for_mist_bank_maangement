from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    path('report/', views.TransactionReportView.as_view(), name='transaction_report'),
    path('deposit/', views.DepositMoneyView.as_view(), name='deposit_money'),
    path('withdraw/', views.WithdrawMoneyView.as_view(), name='withdraw_money'),
    path('withdraw/external/', views.ExternalWithdrawView.as_view(), name='external_withdraw'),
    path('transfer/', views.TransferMoneyView.as_view(), name='transfer_money'),
    path('transfer/external/', views.ExternalTransferView.as_view(), name='external_transfer'),
    # Loan endpoints
    path('loan_request/', views.loan_apply, name='loan_request'),
    path('loans/', views.loan_list, name='loan_list'),
    path('loans/apply/', views.loan_apply, name='loan_apply'),
    path('loans/pay/<int:pk>/', views.pay_loan, name='loan_pay'),
    path('admin/report/', views.admin_loan_report, name='admin_loan_report'),
]