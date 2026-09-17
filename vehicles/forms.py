from django import forms

from . import models


class BorrowDetailForm(forms.ModelForm):
    class Meta:
        model = models.BorrowDetail
        fields = ('borrowers_name', 'destination')


class ReturnDetailForm(forms.ModelForm):
    class Meta:
        model = models.BorrowDetail
        fields = ('fuel_percent', 'current_mileage')