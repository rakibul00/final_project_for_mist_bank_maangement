from django.shortcuts import render
from django.views.generic import FormView
from .forms import UserRegistrationForm,UserUpdateForm, AccountCloseForm, AccountClosureRequestForm
from django.contrib.auth import login, logout
from django.urls import reverse_lazy
from django.contrib.auth.views import LoginView, LogoutView
from django.views import View
from django.shortcuts import redirect
from django.contrib import messages
from .models import AccountClosure, AccountClosureRequest
from notifications.models import Notification

class UserRegistrationView(FormView):
    template_name = 'accounts/user_registration.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('profile')
    
    def form_valid(self,form):
        print(form.cleaned_data)
        user = form.save()
        login(self.request, user)
        print(user)
        return super().form_valid(form) # form_valid function call hobe jodi sob thik thake
    

class UserLoginView(LoginView):
    template_name = 'accounts/user_login.html'
    def get_success_url(self):
        return reverse_lazy('profile')

def user_logout(request):
    logout(request)
    return redirect('login')


class UserBankAccountUpdateView(View):
    template_name = 'accounts/profile.html'

    def dispatch(self, request, *args, **kwargs):
        # Check if user has an active account for updates
        if hasattr(request.user, 'account') and not request.user.account.is_active:
            messages.error(request, 'Your account is closed. You cannot update your profile.')
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = UserUpdateForm(instance=request.user)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')  # Redirect to the user's profile page
        return render(request, self.template_name, {'form': form})
    
    
class AccountCloseView(FormView):
    template_name = 'accounts/account_close.html'  # We'll create this template
    form_class = AccountCloseForm
    success_url = reverse_lazy('profile')  # Redirect to profile after closing

    def form_valid(self, form):
        # Get the user's account
        account = self.request.user.account
        # Create the closure record
        AccountClosure.objects.create(
            account=account,
            reason=form.cleaned_data['reason']
        )
        # Mark account as inactive
        account.is_active = False
        account.save()
        # Optionally, send notification (we can add this later)
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Ensure only the user's own account can be closed
        if not hasattr(self.request.user, 'account'):
            # Handle case where user has no account
            pass
        return kwargs


class RequestAccountClosureView(FormView):
    template_name = 'accounts/request_account_closure.html'
    form_class = AccountClosureRequestForm
    success_url = reverse_lazy('profile')

    def form_valid(self, form):
        # Create the closure request
        request_obj = AccountClosureRequest.objects.create(
            user=self.request.user,
            reason=form.cleaned_data['reason']
        )
        # Send notification to admins
        from django.contrib.auth.models import User
        admins = User.objects.filter(is_staff=True)
        for admin in admins:
            Notification.objects.create(
                user=admin,
                message=f"New account closure request from {self.request.user.username}: {form.cleaned_data['reason'][:100]}..."
            )
        # Show success message
        from django.contrib import messages
        messages.success(self.request, 'Your request has been sent to admin for approval.')
        return super().form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        # Only allow logged-in users
        if not request.user.is_authenticated:
            return redirect('login')
        # Check if user already has a pending request
        if AccountClosureRequest.objects.filter(user=request.user, is_approved=False).exists():
            from django.contrib import messages
            messages.warning(request, 'You already have a pending closure request.')
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)    