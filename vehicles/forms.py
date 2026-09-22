from django import forms

from . import models


class BorrowDetailForm(forms.ModelForm):
    class Meta:
        model = models.BorrowDetail
        fields = ('borrowers_name', 'destination')


class ReturnDetailForm(forms.ModelForm):
    class Meta:
        model = models.BorrowDetail
        fields = ('fuel_percent', 'current_mileage', 'notes')


class ReservationForm(forms.ModelForm):
    class Meta:
        model = models.Reservation
        fields = ('borrowers_name', 'destination', 'start_date', 'end_date', 'notes')
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class PickupCodeForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        label='Pickup code',
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. A7K2',
            'autocomplete': 'off',
            'autocapitalize': 'characters',
            'style': 'text-transform: uppercase; letter-spacing: 0.3em; text-align: center; font-size: 1.5rem;',
        }),
    )

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()