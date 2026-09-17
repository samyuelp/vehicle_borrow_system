from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from . import forms, models


# 1. Home screen — Borrow or Return
class HomeView(TemplateView):
    template_name = 'home.html'


# 2. List of available cars (Borrow flow)
class AvailableCarListView(ListView):
    model = models.Vehicle
    template_name = 'borrow_list.html'
    context_object_name = 'vehicles'

    def get_queryset(self):
        return models.Vehicle.objects.filter(is_available=True)


# 3. Borrow form (name + destination)
class BorrowCarView(CreateView):
    model = models.BorrowDetail
    form_class = forms.BorrowDetailForm
    template_name = 'borrow_form.html'
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        vehicle = models.Vehicle.objects.get(pk=self.kwargs['vehicle_id'])

        form.instance.car_name = vehicle
        response = super().form_valid(form)

        vehicle.is_available = False
        vehicle.save()

        return response


# 4. List of cars currently borrowed (Return flow)
class BorrowedCarListView(ListView):
    model = models.BorrowDetail
    template_name = 'return_list.html'
    context_object_name = 'borrows'

    def get_queryset(self):
        return models.BorrowDetail.objects.filter(return_time__isnull=True)


# 5. Confirm screen — "Is this you?"
class ConfirmBorrowerView(DetailView):
    model = models.BorrowDetail
    template_name = 'return_confirm.html'
    context_object_name = 'borrow'


# 6. Return form (mileage + fuel %)
class ReturnCarView(UpdateView):
    model = models.BorrowDetail
    form_class = forms.ReturnDetailForm
    template_name = 'return_form.html'
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        form.instance.return_time = timezone.now()
        response = super().form_valid(form)

        vehicle = form.instance.car_name
        vehicle.is_available = True
        vehicle.save()

        return response