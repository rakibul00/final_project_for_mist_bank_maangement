from django import forms
from .models import BranchChangeRequest, Branch

class BranchChangeRequestForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            # Exclude current branch from requested branch options if user has a branch
            current_branch = self.user.account.branch if self.user.account else None
            if current_branch:
                self.fields['requested_branch'].queryset = Branch.objects.exclude(id=current_branch.id)
            else:
                self.fields['requested_branch'].queryset = Branch.objects.all()

    class Meta:
        model = BranchChangeRequest
        fields = ['requested_branch', 'request_message']
        widgets = {
            'requested_branch': forms.Select(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
                'required': True,
            }),
            'request_message': forms.Textarea(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
                'rows': 4,
                'placeholder': 'Please explain your reason for requesting a branch change...',
                'maxlength': 500,
                'required': True,
            }),
        }