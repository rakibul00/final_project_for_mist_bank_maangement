
from django.contrib.auth.forms import UserCreationForm
from django import forms
from .constants import ACCOUNT_TYPE, GENDER_TYPE
from django.contrib.auth.models import User
from .models import UserBankAccount, UserAddress, AccountClosure, AccountClosureRequest, ExternalBankAccount
from banks.models import Bank
from branch_management.models import Branch

class UserRegistrationForm(UserCreationForm):
    birth_date = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))
    gender = forms.ChoiceField(choices=GENDER_TYPE)
    account_type = forms.ChoiceField(choices=ACCOUNT_TYPE)
    street_address = forms.CharField(max_length=100)
    city = forms.CharField(max_length= 100)
    postal_code = forms.IntegerField()
    country = forms.CharField(max_length=100)
    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'first_name', 'last_name', 'email', 'account_type', 'birth_date','gender', 'postal_code', 'city','country', 'street_address']
        
        # form.save()
    def save(self, commit=True):
        our_user = super().save(commit=False) # ami database e data save korbo na ekhn
        if commit == True:
            our_user.save() # user model e data save korlam
            account_type = self.cleaned_data.get('account_type')
            gender = self.cleaned_data.get('gender')
            postal_code = self.cleaned_data.get('postal_code')
            country = self.cleaned_data.get('country')
            birth_date = self.cleaned_data.get('birth_date')
            city = self.cleaned_data.get('city')
            street_address = self.cleaned_data.get('street_address')
            
            UserAddress.objects.create(
                user = our_user,
                postal_code = postal_code,
                country = country,
                city = city,
                street_address = street_address
            )
            # Ensure a default bank exists; create one if missing to avoid DoesNotExist
            default_bank, _created = Bank.objects.get_or_create(
                name='Default Bank',
                defaults={'code': 'DEF', 'is_active': True}
            )
            UserBankAccount.objects.create(
                user = our_user,
                bank = default_bank,
                branch = Branch.objects.get_or_create(name='Main Branch', defaults={'code': 'MAIN', 'address': 'Default Address'})[0],
                account_type  = account_type,
                gender = gender,
                birth_date =birth_date,
                account_no = 100000+ our_user.id
            )
        return our_user
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                
                'class' : (
                    'appearance-none block w-full bg-gray-200 '
                    'text-gray-700 border border-gray-200 rounded '
                    'py-3 px-4 leading-tight focus:outline-none '
                    'focus:bg-white focus:border-gray-500'
                ) 
            })


# profile ki ki jinis update korte parbe amader user

class UserUpdateForm(forms.ModelForm):
    birth_date = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))
    gender = forms.ChoiceField(choices=GENDER_TYPE)
    account_type = forms.ChoiceField(choices=ACCOUNT_TYPE)
    street_address = forms.CharField(max_length=100)
    city = forms.CharField(max_length= 100)
    postal_code = forms.IntegerField()
    country = forms.CharField(max_length=100)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': (
                    'appearance-none block w-full bg-gray-200 '
                    'text-gray-700 border border-gray-200 rounded '
                    'py-3 px-4 leading-tight focus:outline-none '
                    'focus:bg-white focus:border-gray-500'
                )
            })
        # jodi user er account thake 
        if self.instance:
            try:
                user_account = self.instance.account
                user_address = self.instance.address
            except UserBankAccount.DoesNotExist:
                user_account = None
                user_address = None

            if user_account:
                self.fields['account_type'].initial = user_account.account_type
                self.fields['gender'].initial = user_account.gender
                self.fields['birth_date'].initial = user_account.birth_date
                self.fields['street_address'].initial = user_address.street_address
                self.fields['city'].initial = user_address.city
                self.fields['postal_code'].initial = user_address.postal_code
                self.fields['country'].initial = user_address.country

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()

            user_account, created = UserBankAccount.objects.get_or_create(user=user) # jodi account thake taile seta jabe user_account ar jodi account na thake taile create hobe ar seta created er moddhe jabe
            user_address, created = UserAddress.objects.get_or_create(user=user) 

            user_account.account_type = self.cleaned_data['account_type']
            user_account.gender = self.cleaned_data['gender']
            user_account.birth_date = self.cleaned_data['birth_date']
            user_account.save()

            user_address.street_address = self.cleaned_data['street_address']
            user_address.city = self.cleaned_data['city']
            user_address.postal_code = self.cleaned_data['postal_code']
            user_address.country = self.cleaned_data['country']
            user_address.save()

        return user


class AccountCloseForm(forms.ModelForm):
    reason = forms.CharField(
        max_length=300,
        widget=forms.Textarea(attrs={
            'placeholder': 'Write your reason for closing the account',
            'class': 'appearance-none block w-full bg-gray-200 text-gray-700 border border-gray-200 rounded py-3 px-4 leading-tight focus:outline-none focus:bg-white focus:border-gray-500',
            'rows': 4
        }),
        label='Reason for closing account'
    )

    class Meta:
        model = AccountClosure
        fields = ['reason']


class AccountClosureRequestForm(forms.ModelForm):
    reason = forms.CharField(
        max_length=300,
        widget=forms.Textarea(attrs={
            'placeholder': 'Write your reason for closing the account',
            'class': 'appearance-none block w-full bg-gray-200 text-gray-700 border border-gray-200 rounded py-3 px-4 leading-tight focus:outline-none focus:bg-white focus:border-gray-500',
            'rows': 4
        }),
        label='Reason for requesting account closure'
    )

    class Meta:
        model = AccountClosureRequest
        fields = ['reason']


class ExternalBankAccountForm(forms.ModelForm):
    account_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter account number'
        }),
        label='Account Number'
    )
    
    current_balance = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01'
        }),
        label='Current Balance',
        min_value=0
    )

    class Meta:
        model = ExternalBankAccount
        fields = ['bank', 'account_number', 'current_balance']
        widgets = {
            'bank': forms.Select(attrs={'class': 'form-control'}),
        }


class ExternalBankAccountCreateForm(forms.ModelForm):
    bank = forms.ModelChoiceField(queryset=Bank.objects.filter(is_active=True), widget=forms.Select(attrs={'class': 'form-control'}))
    current_balance = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01'
        }),
        label='Current Balance',
        min_value=0
    )

    class Meta:
        model = ExternalBankAccount
        fields = ['bank', 'current_balance']

    def __init__(self, *args, **kwargs):
        # Accept `prefill_bank` kwarg (Bank instance or id) to disable bank selection
        prefill_bank = kwargs.pop('prefill_bank', None)
        super().__init__(*args, **kwargs)
        if prefill_bank:
            # allow passing either Bank instance or id
            from banks.models import Bank as BankModel
            if isinstance(prefill_bank, BankModel):
                bank_obj = prefill_bank
            else:
                bank_obj = Bank.objects.filter(pk=prefill_bank).first()
            if bank_obj:
                self.fields['bank'].initial = bank_obj
                self.fields['bank'].queryset = Bank.objects.filter(pk=bank_obj.pk)
                self.fields['bank'].disabled = True

    def clean_current_balance(self):
        bal = self.cleaned_data.get('current_balance')
        if bal is None:
            return 0
        if bal < 0:
            raise forms.ValidationError('Balance must be zero or a positive number.')
        return bal