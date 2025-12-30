from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db import transaction as db_transaction, models
from django.core.exceptions import ValidationError
from .services import BalanceService, InsufficientBalanceError
from decimal import Decimal
from django.contrib.admin.views.decorators import staff_member_required

from .models import Loan, LoanPayment, Transaction
from .forms import LoanApplyForm


@login_required
def loan_apply(request):
    """Allow logged-in users to apply for a loan."""
    account = getattr(request.user, 'account', None)
    if account is None:
        messages.error(request, 'No bank account associated with your user.')
        return redirect('transactions:loan_list')

    if request.method == 'POST':
        form = LoanApplyForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.user = account
            loan.status = Loan.STATUS_PENDING
            loan.applied_date = timezone.now()
            loan.save()
            messages.success(request, 'Loan application submitted successfully.')
            return redirect('transactions:loan_list')
    else:
        form = LoanApplyForm()

    return render(request, 'transactions/loan_request.html', {'form': form})


@login_required
def loan_list(request):
    account = getattr(request.user, 'account', None)
    if account is None:
        messages.error(request, 'No bank account found for your user.')
        return redirect('/')

    loans = Loan.objects.filter(user=account).order_by('-applied_date')
    return render(request, 'transactions/loan_list.html', {'loans': loans})


@login_required
def pay_loan(request, pk):
    account = getattr(request.user, 'account', None)
    loan = get_object_or_404(Loan, pk=pk, user=account)

    if loan.status != Loan.STATUS_APPROVED:
        messages.error(request, 'Only approved loans can be paid.')
        return redirect('transactions:loan_list')

    if request.method == 'POST':
        try:
            payment_amount = Decimal(request.POST.get('amount', '0'))
        except:
            messages.error(request, 'Invalid payment amount.')
            return redirect('transactions:loan_pay', pk=loan.pk)

        if payment_amount <= Decimal('0'):
            messages.error(request, 'Payment amount must be greater than zero.')
            return redirect('transactions:loan_pay', pk=loan.pk)

        total_paid = loan.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        remaining = loan.total_amount - total_paid

        if payment_amount > remaining:
            messages.error(request, f'Payment amount cannot exceed remaining balance of {remaining}.')
            return redirect('transactions:loan_pay', pk=loan.pk)

        with db_transaction.atomic():
            account.refresh_from_db()
            if account.balance < payment_amount:
                messages.error(request, 'Insufficient balance to make this payment.')
                return redirect('transactions:loan_pay', pk=loan.pk)

            # Deduct balance
            account.balance -= payment_amount
            account.save()

            # Create payment record
            payment = LoanPayment.objects.create(
                loan=loan,
                payer=account,
                amount=payment_amount,
            )

            # Create a transaction record for audit
            Transaction.objects.create(
                account=account,
                amount=-payment_amount,
                balance_after_transaction=account.balance,
                transaction_type=4,  # Loan Paid
                note=f'Loan payment for Loan {loan.id}'
            )

            # Check if fully paid
            new_total_paid = total_paid + payment_amount
            if new_total_paid >= loan.total_amount:
                loan.status = Loan.STATUS_PAID
                loan.paid_date = timezone.now()
                loan.save()

            messages.success(request, f'Payment of {payment_amount} made successfully.')
            return redirect('transactions:loan_list')

    return render(request, 'transactions/loan_pay.html', {'loan': loan})


def is_staff(user):
    return user.is_active and user.is_staff


@user_passes_test(is_staff)
def admin_loan_report(request):
    from django.db.models import Sum

    total_loans = Loan.objects.count()
    approved_loans = Loan.objects.filter(status=Loan.STATUS_APPROVED).count()
    pending_loans = Loan.objects.filter(status=Loan.STATUS_PENDING).count()
    rejected_loans = Loan.objects.filter(status=Loan.STATUS_REJECTED).count()
    total_approved_amount = Loan.objects.filter(status=Loan.STATUS_APPROVED).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    context = {
        'total_loans': total_loans,
        'approved_loans': approved_loans,
        'pending_loans': pending_loans,
        'rejected_loans': rejected_loans,
        'total_approved_amount': total_approved_amount,
    }
    return render(request, 'transactions/admin_report.html', context)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.http import HttpResponse
from django.views.generic import CreateView, ListView
from transactions.constants import DEPOSIT, WITHDRAWAL,LOAN, LOAN_PAID, TRANSFER
from datetime import datetime
from django.db.models import Sum
from transactions.forms import (
    DepositForm,
    WithdrawForm,
    LoanRequestForm,
)
from transactions.forms import TransferForm
from django.shortcuts import render
from django.db import transaction as db_transaction
from transactions.models import Transaction, Loan, LoanPayment
from accounts.models import UserBankAccount

class TransactionCreateMixin(LoginRequiredMixin, CreateView):
    template_name = 'transactions/transaction_form.html'
    model = Transaction
    title = ''
    success_url = reverse_lazy('transactions:transaction_report')

    def dispatch(self, request, *args, **kwargs):
        # Check if user has an active account
        if hasattr(request.user, 'account') and not request.user.account.is_active:
            messages.error(request, 'Your account is closed. You cannot perform transactions.')
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'account': self.request.user.account
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs) # template e context data pass kora
        context.update({
            'title': self.title
        })

        return context


class DepositMoneyView(TransactionCreateMixin):
    form_class = DepositForm
    title = 'Deposit'

    def get_initial(self):
        initial = {'transaction_type': DEPOSIT}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')
        account = self.request.user.account
        # if not account.initial_deposit_date:
        #     now = timezone.now()
        #     account.initial_deposit_date = now
        account.balance += amount # amount = 200, tar ager balance = 0 taka new balance = 0+200 = 200
        account.save(
            update_fields=[
                'balance'
            ]
        )

        # Set transaction type
        form.instance.transaction_type = DEPOSIT

        messages.success(
            self.request,
            f'{"{:,.2f}".format(float(amount))}$ was deposited to your account successfully'
        )

        return super().form_valid(form)


class WithdrawMoneyView(TransactionCreateMixin):
    form_class = WithdrawForm
    title = 'Withdraw Money'

    def get_initial(self):
        initial = {'transaction_type': WITHDRAWAL}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')
        account = self.request.user.account

        try:
            from .services import BalanceService
            # Use service layer for balance validation and update
            transaction_record = BalanceService.withdraw_from_main_account(
                user_account=account,
                amount=amount,
                note=f'Withdrawal of ${amount}'
            )

            messages.success(
                self.request,
                f'Successfully withdrawn ${amount} from your account. New balance: ${account.balance}'
            )

            return super().form_valid(form)

        except InsufficientBalanceError as e:
            # Pass error context to template for better UI display
            context = {
                'form': form,
                'insufficient_balance_error': e.get_context(),
                'title': self.title
            }
            return render(self.request, self.template_name, context)
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)

class LoanRequestView(LoginRequiredMixin, CreateView):
    model = Loan
    form_class = LoanRequestForm
    template_name = 'transactions/loan_request.html'
    success_url = reverse_lazy('loan_list')

    def dispatch(self, request, *args, **kwargs):
        # Check if user has an active account
        if hasattr(request.user, 'account') and not request.user.account.is_active:
            messages.error(request, 'Your account is closed. You cannot request loans.')
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        loan = form.save(commit=False)
        loan.user = self.request.user.account
        loan.status = 'Active'  # Auto-approve for simplicity
        loan.approved_at = timezone.now()
        loan.save()
        messages.success(self.request, f'Loan request for ${loan.loan_amount} submitted and approved successfully')
        return redirect(self.success_url)
    
class TransactionReportView(LoginRequiredMixin, ListView):
    template_name = 'transactions/transaction_report.html'
    model = Transaction
    balance = 0 # filter korar pore ba age amar total balance ke show korbe

    def dispatch(self, request, *args, **kwargs):
        # Check if user has an active account
        if hasattr(request.user, 'account') and not request.user.account.is_active:
            messages.error(request, 'Your account is closed. You cannot view transactions.')
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Include both main account transactions and external account transactions
        queryset = Transaction.objects.filter(
            models.Q(account=self.request.user.account) |
            models.Q(external_account__user=self.request.user)
        )
        start_date_str = self.request.GET.get('start_date')
        end_date_str = self.request.GET.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            queryset = queryset.filter(timestamp__date__gte=start_date, timestamp__date__lte=end_date)
            self.balance = Transaction.objects.filter(
                models.Q(account=self.request.user.account) |
                models.Q(external_account__user=self.request.user),
                timestamp__date__gte=start_date, timestamp__date__lte=end_date
            ).aggregate(Sum('amount'))['amount__sum']
        else:
            self.balance = self.request.user.account.balance
       
        return queryset.distinct().order_by('-timestamp') # unique queryset hote hobe
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'account': self.request.user.account,
            'external_accounts': self.request.user.external_accounts.all(),
            'total_balance': self.request.user.account.total_balance,
            'external_total': self.request.user.account.external_accounts_balance,
        })

        return context
    
class PayLoanView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        # Check if user has an active account
        if hasattr(request.user, 'account') and not request.user.account.is_active:
            messages.error(request, 'Your account is closed. You cannot pay loans.')
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, loan_id):
        loan = get_object_or_404(Loan, id=loan_id, user=request.user.account)

        # Check if loan is active and has remaining amount
        if loan.status != 'Active':
            messages.error(request, 'This loan is not active for payments.')
            return redirect('loan_list')

        if loan.remaining_amount <= 0:
            messages.error(request, 'This loan is already fully paid.')
            return redirect('loan_list')

        # Check if user has sufficient balance
        if request.user.account.balance < loan.monthly_installment:
            messages.error(request, f'Insufficient balance. You need ${loan.monthly_installment} but have ${request.user.account.balance}.')
            return redirect('loan_list')

        # Process payment using atomic transaction
        with db_transaction.atomic():
            # Deduct from user balance
            request.user.account.balance -= loan.monthly_installment
            request.user.account.save(update_fields=['balance'])

            # Reduce remaining amount
            loan.remaining_amount -= loan.monthly_installment

            # Create payment record
            installment_number = loan.payments.count() + 1
            LoanPayment.objects.create(
                loan=loan,
                user=request.user.account,
                amount=loan.monthly_installment,
                installment_number=installment_number
            )

            # Check if loan is fully paid
            if loan.remaining_amount <= 0:
                loan.status = 'Paid'
                loan.remaining_amount = 0  # Ensure it's exactly 0

            # Update due date for next payment (if not fully paid)
            if loan.status == 'Active':
                from datetime import date, timedelta
                loan.due_date = date.today() + timedelta(days=30)

            loan.save()

            # Create transaction record
            Transaction.objects.create(
                account=request.user.account,
                bank=request.user.account.bank,
                amount=loan.monthly_installment,
                balance_after_transaction=request.user.account.balance,
                transaction_type=LOAN_PAID,
                is_incoming=False
            )

        messages.success(request, f'Successfully paid ${loan.monthly_installment} towards loan #{loan.id}')
        return redirect('loan_list')


class PayFullLoanView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        # Check if user has an active account
        if hasattr(request.user, 'account') and not request.user.account.is_active:
            messages.error(request, 'Your account is closed. You cannot pay loans.')
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, loan_id):
        loan = get_object_or_404(Loan, id=loan_id, user=request.user.account)

        # Check if loan is active and has remaining amount
        if loan.status != 'Active':
            messages.error(request, 'This loan is not active for payments.')
            return redirect('loan_list')

        if loan.remaining_amount <= 0:
            messages.error(request, 'This loan is already fully paid.')
            return redirect('loan_list')

        # Check if user has sufficient balance
        if request.user.account.balance < loan.remaining_amount:
            messages.error(request, f'Insufficient balance. You need ${loan.remaining_amount} but have ${request.user.account.balance}.')
            return redirect('loan_list')

        # Process full payment using atomic transaction
        with db_transaction.atomic():
            # Store the payment amount before changing loan
            payment_amount = loan.remaining_amount

            # Deduct from user balance
            request.user.account.balance -= payment_amount
            request.user.account.save(update_fields=['balance'])

            # Create payment record for the full amount
            installment_number = loan.payments.count() + 1
            LoanPayment.objects.create(
                loan=loan,
                user=request.user.account,
                amount=payment_amount,
                installment_number=installment_number
            )

            # Mark loan as fully paid
            loan.status = 'Paid'
            loan.remaining_amount = 0
            loan.save()

            # Create transaction record
            Transaction.objects.create(
                account=request.user.account,
                bank=request.user.account.bank,
                amount=payment_amount,
                balance_after_transaction=request.user.account.balance,
                transaction_type=LOAN_PAID,
                is_incoming=False
            )

        messages.success(request, f'Successfully paid full amount of ${payment_amount} for loan #{loan.id}. Loan is now fully paid!')
        return redirect('loan_list')


class LoanPaymentView(LoginRequiredMixin, View):
    def get(self, request, loan_id):
        loan = get_object_or_404(Loan, id=loan_id, user=request.user.account, status='Active')
        form = LoanPaymentForm(loan=loan, account=request.user.account)
        return render(request, 'transactions/loan_payment.html', {
            'loan': loan,
            'form': form,
            'title': 'Pay Loan'
        })

    def post(self, request, loan_id):
        loan = get_object_or_404(Loan, id=loan_id, user=request.user.account, status='Active')
        form = LoanPaymentForm(request.POST, loan=loan, account=request.user.account)
        if form.is_valid():
            # Process payment
            payment_amount = form.cleaned_data['amount']
            payment_date = form.cleaned_data['payment_date']

            with db_transaction.atomic():
                # Deduct from balance
                request.user.account.balance -= payment_amount
                request.user.account.save(update_fields=['balance'])

                # Create payment record
                LoanPayment.objects.create(
                    loan=loan,
                    user=request.user.account,
                    amount=payment_amount,
                    payment_date=payment_date
                )

                # Mark loan as paid
                loan.status = 'Paid'
                loan.save()

                # Create transaction record
                Transaction.objects.create(
                    account=request.user.account,
                    bank=request.user.account.bank,
                    amount=payment_amount,
                    balance_after_transaction=request.user.account.balance,
                    transaction_type=LOAN_PAID,
                    is_incoming=False
                )

            messages.success(request, f'Loan payment of ${payment_amount} processed successfully.')
            return redirect('loan_list')
        return render(request, 'transactions/loan_payment.html', {
            'loan': loan,
            'form': form,
            'title': 'Pay Loan'
        })


class LoanListView(LoginRequiredMixin, ListView):
    model = Loan
    template_name = 'transactions/loan_list.html'
    context_object_name = 'loans'

    def dispatch(self, request, *args, **kwargs):
        # Check if user has an active account
        if hasattr(request.user, 'account') and not request.user.account.is_active:
            messages.error(request, 'Your account is closed. You cannot view loans.')
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Return all loans for the user ordered by application date
        return Loan.objects.filter(user=self.request.user.account).order_by('-applied_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_loans = self.get_queryset()
        context['active_loans_count'] = Loan.objects.filter(user=self.request.user.account, status=Loan.STATUS_APPROVED).count()
        context['paid_loans_count'] = Loan.objects.filter(user=self.request.user.account, status=Loan.STATUS_PAID).count()
        return context


class TransferMoneyView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        # Check if user has an active account
        if hasattr(request.user, 'account') and not request.user.account.is_active:
            messages.error(request, 'Your account is closed. You cannot transfer money.')
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = TransferForm(account=request.user.account)
        return render(request, 'transactions/transfer.html', {'form': form, 'title': 'Transfer Money'})

    def post(self, request):
        form = TransferForm(request.POST, account=request.user.account)
        if form.is_valid():
            amount = form.cleaned_data.get('amount')
            recipient = form.cleaned_data.get('recipient')

            sender = request.user.account

            try:
                from .services import BalanceService
                # Use service layer for transfer validation and update
                sender_transaction, recipient_transaction = BalanceService.transfer_from_main_account(
                    sender_account=sender,
                    recipient_account=recipient,
                    amount=amount,
                    note=f'Transfer to {recipient.user.username}'
                )

                messages.success(request, f'Successfully transferred ${amount} to account {recipient.account_no}')
                return redirect('transactions:transaction_report')

            except InsufficientBalanceError as e:
                # Pass error context to template for better UI display
                context = {
                    'form': form,
                    'insufficient_balance_error': e.get_context(),
                    'title': 'Transfer Money'
                }
                return render(request, 'transactions/transfer.html', context)
            except ValidationError as e:
                messages.error(request, str(e))
                return render(request, 'transactions/transfer.html', {'form': form, 'title': 'Transfer Money'})

        return render(request, 'transactions/transfer.html', {'form': form, 'title': 'Transfer Money'})


class ExternalWithdrawView(LoginRequiredMixin, View):
    """View for withdrawing money from external accounts"""

    def dispatch(self, request, *args, **kwargs):
        # Check if user has an active account
        if hasattr(request.user, 'account') and not request.user.account.is_active:
            messages.error(request, 'Your account is closed. You cannot perform external withdrawals.')
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        from .forms import ExternalWithdrawForm
        form = ExternalWithdrawForm(user=request.user)
        return render(request, 'transactions/external_withdraw.html', {'form': form, 'title': 'Withdraw from External Account'})

    def post(self, request):
        from .forms import ExternalWithdrawForm
        form = ExternalWithdrawForm(request.POST, user=request.user)
        if form.is_valid():
            external_account = form.cleaned_data.get('external_account')
            amount = form.cleaned_data.get('amount')
            note = form.cleaned_data.get('note', '')

            try:
                from .services import BalanceService
                # Use service layer for balance validation and update
                transaction_record = BalanceService.withdraw_from_external_account(
                    user=request.user,
                    external_account=external_account,
                    amount=amount,
                    note=note or f'Withdrawal from external account {external_account.account_number}'
                )

                # Send notification
                from notifications.models import Notification
                Notification.objects.create(
                    user=request.user,
                    message=f'Successfully withdrawn ${amount} from external account {external_account.account_number}. New balance: ${external_account.current_balance}'
                )

                messages.success(request, f'Successfully withdrawn ${amount} from external account {external_account.account_number}')
                return redirect('transactions:transaction_report')

            except InsufficientBalanceError as e:
                # Pass error context to template for better UI display
                context = {
                    'form': form,
                    'insufficient_balance_error': e.get_context(),
                    'title': 'Withdraw from External Account'
                }
                return render(request, 'transactions/external_withdraw.html', context)
            except ValidationError as e:
                messages.error(request, str(e))
                return render(request, 'transactions/external_withdraw.html', {'form': form, 'title': 'Withdraw from External Account'})

        return render(request, 'transactions/external_withdraw.html', {'form': form, 'title': 'Withdraw from External Account'})


class ExternalTransferView(LoginRequiredMixin, View):
    """View for transferring money from external accounts to other users"""

    def dispatch(self, request, *args, **kwargs):
        # Check if user has an active account
        if hasattr(request.user, 'account') and not request.user.account.is_active:
            messages.error(request, 'Your account is closed. You cannot perform external transfers.')
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        from .forms import ExternalTransferForm
        form = ExternalTransferForm(user=request.user)
        return render(request, 'transactions/external_transfer.html', {'form': form, 'title': 'Transfer from External Account'})

    def post(self, request):
        from .forms import ExternalTransferForm
        form = ExternalTransferForm(request.POST, user=request.user)
        if form.is_valid():
            from_external_account = form.cleaned_data.get('from_external_account')
            recipient = form.cleaned_data.get('recipient')
            amount = form.cleaned_data.get('amount')
            note = form.cleaned_data.get('note', '')

            try:
                from .services import BalanceService
                # Use service layer for transfer validation and update
                sender_transaction, recipient_transaction = BalanceService.transfer_from_external_account(
                    user=request.user,
                    external_account=from_external_account,
                    recipient_account=recipient,
                    amount=amount,
                    note=note or f'Transfer from external account to {recipient.user.username}'
                )

                # Send notifications
                from notifications.models import Notification
                Notification.objects.create(
                    user=request.user,
                    message=f'Successfully transferred ${amount} from external account {from_external_account.account_number} to {recipient.user.username}'
                )

                Notification.objects.create(
                    user=recipient.user,
                    message=f'Received ${amount} transfer from {request.user.username} (external account)'
                )

                messages.success(request, f'Successfully transferred ${amount} from external account to {recipient.user.username}')
                return redirect('transactions:transaction_report')

            except InsufficientBalanceError as e:
                # Pass error context to template for better UI display
                context = {
                    'form': form,
                    'insufficient_balance_error': e.get_context(),
                    'title': 'Transfer from External Account'
                }
                return render(request, 'transactions/external_transfer.html', context)
            except ValidationError as e:
                messages.error(request, str(e))
                return render(request, 'transactions/external_transfer.html', {'form': form, 'title': 'Transfer from External Account'})

        return render(request, 'transactions/external_transfer.html', {'form': form, 'title': 'Transfer from External Account'})