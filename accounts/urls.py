
from django.urls import path
from .import views
from .views import UserRegistrationView, UserLoginView, user_logout,UserBankAccountUpdateView, AccountCloseView, RequestAccountClosureView, ExternalBankAccountListView, ExternalBankAccountCreateView, ExternalBankAccountUpdateView, ExternalBankAccountDeleteView
 
urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', views.user_logout, name = 'logout'),
    path('profile/', UserBankAccountUpdateView.as_view(), name='profile' ),
    path('close/', AccountCloseView.as_view(), name='account_close'),
    path('close/request/', RequestAccountClosureView.as_view(), name='request_account_closure'),
    path('external-accounts/', ExternalBankAccountListView.as_view(), name='external_accounts'),
    path('external-accounts/add/', ExternalBankAccountCreateView.as_view(), name='add_external_account'),
    path('available-banks/', views.AvailableBanksView.as_view(), name='available_banks'),
    path('external-accounts/add/<int:bank_id>/', views.AddExternalBankView.as_view(), name='add_external_bank'),
    path('external-accounts/<int:pk>/edit/', ExternalBankAccountUpdateView.as_view(), name='edit_external_account'),
    path('external-accounts/<int:pk>/delete/', ExternalBankAccountDeleteView.as_view(), name='delete_external_account'),
]