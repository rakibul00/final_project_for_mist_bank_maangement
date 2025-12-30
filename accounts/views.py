from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import FormView
from .forms import UserRegistrationForm,UserUpdateForm, AccountCloseForm, AccountClosureRequestForm, ExternalBankAccountForm, ExternalBankAccountCreateForm
from django.contrib.auth import login, logout
from django.urls import reverse_lazy
from django.contrib.auth.views import LoginView, LogoutView
from django.views import View
from django.shortcuts import redirect
from django.contrib import messages
from .models import AccountClosure, AccountClosureRequest, ExternalBankAccount
from django.contrib.auth.mixins import LoginRequiredMixin
from banks.models import Bank
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


class ExternalBankAccountListView(View):
    template_name = 'accounts/external_accounts.html'

    def get(self, request):
        external_accounts = ExternalBankAccount.objects.filter(user=request.user)
        total_external_balance = sum(account.current_balance for account in external_accounts)
        main_balance = request.user.account.balance if hasattr(request.user, 'account') else 0
        total_aggregated_balance = main_balance + total_external_balance
        
        context = {
            'external_accounts': external_accounts,
            'total_external_balance': total_external_balance,
            'main_balance': main_balance,
            'total_aggregated_balance': total_aggregated_balance,
        }
        return render(request, self.template_name, context)


class ExternalBankAccountCreateView(LoginRequiredMixin, View):
    template_name = 'accounts/add_external_account.html'

    def get(self, request):
        bank_id = request.GET.get('bank_id')
        prefill = None
        if bank_id:
            prefill = Bank.objects.filter(pk=bank_id).first()
        # Use create form that can accept prefill_bank kwarg
        form = ExternalBankAccountCreateForm(prefill_bank=prefill)
        return render(request, self.template_name, {'form': form, 'prefill_bank': prefill})

    def post(self, request):
        bank_id = request.POST.get('bank') or request.GET.get('bank_id')
        prefill = None
        if bank_id:
            prefill = Bank.objects.filter(pk=bank_id).first()

        form = ExternalBankAccountCreateForm(request.POST, prefill_bank=prefill)
        if form.is_valid():
            # Save atomically without modifying main account balance
            from django.db import transaction, IntegrityError
            try:
                with transaction.atomic():
                    external_account = form.save(commit=False)
                    external_account.user = request.user
                    # Ensure bank field is set (either from disabled field or prefill)
                    if prefill and not external_account.bank:
                        external_account.bank = prefill
                    # Account number is now provided by user, no need to generate
                    external_account.save()
                    # DO NOT update user's main bank account balance - external accounts are separate
            except IntegrityError:
                messages.error(request, 'An account with this account number already exists.')
                return render(request, self.template_name, {'form': form, 'prefill_bank': prefill})

            bank_display = external_account.bank.name if external_account.bank else 'Unknown Bank'
            messages.success(request, f'External bank account for {external_account.account_holder_name} added successfully!')
            return redirect('external_accounts')

        return render(request, self.template_name, {'form': form, 'prefill_bank': prefill})


class AvailableBanksView(LoginRequiredMixin, View):
    template_name = 'accounts/available_banks.html'

    def get(self, request):
        banks = Bank.objects.all()
        return render(request, self.template_name, {'banks': banks})


class AddExternalBankView(LoginRequiredMixin, View):
    def post(self, request, bank_id):
        bank = get_object_or_404(Bank, pk=bank_id)
        # prevent duplicates
        obj, created = ExternalBankAccount.objects.get_or_create(
            user=request.user,
            bank=bank,
            defaults={'current_balance': 0, 'account_number': f'{bank.id}-{request.user.id}-{int(request.user.id)}'}
        )
        if created:
            messages.success(request, f'{bank.name} added to your external accounts.')
        else:
            messages.info(request, f'{bank.name} is already in your external accounts.')
        return redirect('external_accounts')


class ExternalBankAccountUpdateView(View):
    template_name = 'accounts/edit_external_account.html'

    def get(self, request, pk):
        account = ExternalBankAccount.objects.get(pk=pk, user=request.user)
        form = ExternalBankAccountForm(instance=account)
        return render(request, self.template_name, {'form': form, 'account': account})

    def post(self, request, pk):
        account = ExternalBankAccount.objects.get(pk=pk, user=request.user)
        form = ExternalBankAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, f'External bank account updated successfully!')
            return redirect('external_accounts')
        return render(request, self.template_name, {'form': form, 'account': account})


class ExternalBankAccountDeleteView(View):
    def post(self, request, pk):
        account = ExternalBankAccount.objects.get(pk=pk, user=request.user)
        bank_display = account.bank.name if account.bank else 'Unknown Bank'
        account.delete()
        messages.success(request, f'External bank account {bank_display} - {account.account_number} deleted successfully!')
        return redirect('external_accounts')