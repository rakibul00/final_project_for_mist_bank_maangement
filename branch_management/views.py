from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, UpdateView
from django.urls import reverse_lazy
from .models import Branch, BranchChangeRequest
from .forms import BranchChangeRequestForm

@login_required
def submit_branch_change_request(request):
    # Check if user already has a pending request
    if BranchChangeRequest.objects.filter(user=request.user, status='Pending').exists():
        messages.error(request, 'You already have a pending branch change request. Please wait for admin approval.')
        return redirect('branch_change_requests')

    if request.method == 'POST':
        form = BranchChangeRequestForm(request.POST, user=request.user)
        if form.is_valid():
            branch_request = form.save(commit=False)
            branch_request.user = request.user
            branch_request.current_branch = request.user.account.branch
            branch_request.save()
            messages.success(request, 'Your branch change request has been submitted successfully.')
            return redirect('branch_change_requests')
    else:
        form = BranchChangeRequestForm(user=request.user)
    return render(request, 'branch_management/submit_request.html', {'form': form})

@login_required
def branch_change_requests(request):
    requests = BranchChangeRequest.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'branch_management/my_requests.html', {'requests': requests})

class BranchChangeRequestListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = BranchChangeRequest
    template_name = 'branch_management/admin_requests.html'
    context_object_name = 'requests'
    ordering = ['-created_at']

    def test_func(self):
        return self.request.user.account.role == 'Admin'

class BranchChangeRequestUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = BranchChangeRequest
    fields = ['status', 'admin_comment']
    template_name = 'branch_management/admin_request_detail.html'
    success_url = reverse_lazy('admin_branch_requests')

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        return self.request.user.account.role == 'Admin'

    def form_valid(self, form):
        instance = form.save(commit=False)
        if instance.status == 'Approved':
            instance.status = 'Approved'
            messages.success(self.request, 'Request approved and user branch updated.')
        elif instance.status == 'Rejected':
            comment = form.cleaned_data.get('admin_comment', '')
            instance.admin_comment = comment
            instance.status = 'Rejected'
            messages.success(self.request, 'Request rejected.')
        return super().form_valid(form)
