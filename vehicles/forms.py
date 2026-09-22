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