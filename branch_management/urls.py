from django.urls import path
from . import views

urlpatterns = [
    path('submit-request/', views.submit_branch_change_request, name='submit_branch_change_request'),
    path('my-requests/', views.branch_change_requests, name='branch_change_requests'),
    path('admin/requests/', views.BranchChangeRequestListView.as_view(), name='admin_branch_requests'),
    path('admin/request/<int:pk>/', views.BranchChangeRequestUpdateView.as_view(), name='admin_request_detail'),
]