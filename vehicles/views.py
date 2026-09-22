from django.shortcuts import render
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


def _vehicle_status(vehicle):
    """Return a dict describing a vehicle's current state."""
    today = timezone.localdate()

    current_borrow = models.BorrowDetail.objects.filter(
        vehicle=vehicle,
        actual_return_time__isnull=True,
    ).first()

    reserved_today = models.Reservation.objects.filter(
        vehicle=vehicle,
        start_date__lte=today,
        end_date__gte=today,
    ).first()

    return {
        'current_borrow': current_borrow,
        'reserved_today': reserved_today,
        'is_available': not current_borrow and not reserved_today,
    }


class HomeView(TemplateView):
    template_name = 'home.html'


# ---------- Borrow flow ----------

class AvailableCarListView(ListView):
    model = models.Vehicle
    template_name = 'borrow_list.html'
    context_object_name = 'vehicles'

    def get_queryset(self):
        return models.Vehicle.objects.all().order_by('car_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for vehicle in context['vehicles']:
            vehicle.status = _vehicle_status(vehicle)
        return context


class BorrowCarView(CreateView):
    model = models.BorrowDetail
    form_class = forms.BorrowDetailForm
    template_name = 'borrow_form.html'
    success_url = reverse_lazy('home')

    def dispatch(self, request, *args, **kwargs):
        vehicle = models.Vehicle.objects.get(pk=kwargs['vehicle_id'])
        status = _vehicle_status(vehicle)
        if not status['is_available']:
            return render(request, 'borrow_unavailable.html', {
                'vehicle': vehicle,
                'status': status,
            })
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['vehicle'] = models.Vehicle.objects.get(pk=self.kwargs['vehicle_id'])
        return context

    def form_valid(self, form):
        vehicle = models.Vehicle.objects.get(pk=self.kwargs['vehicle_id'])
        form.instance.vehicle = vehicle
        return super().form_valid(form)


# ---------- Return flow ----------

class BorrowedCarListView(ListView):
    model = models.BorrowDetail
    template_name = 'return_list.html'
    context_object_name = 'borrows'

    def get_queryset(self):
        return models.BorrowDetail.objects.filter(
            actual_return_time__isnull=True,
        ).order_by('borrow_time')


class ConfirmBorrowerView(DetailView):
    model = models.BorrowDetail
    template_name = 'return_confirm.html'
    context_object_name = 'borrow'


class ReturnCarView(UpdateView):
    model = models.BorrowDetail
    form_class = forms.ReturnDetailForm
    template_name = 'return_form.html'
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        form.instance.actual_return_time = timezone.now()
        return super().form_valid(form)


# ---------- Reserve flow ----------

class ReserveCarListView(ListView):
    model = models.Vehicle
    template_name = 'reserve_list.html'
    context_object_name = 'vehicles'

    def get_queryset(self):
        return models.Vehicle.objects.all().order_by('car_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        for vehicle in context['vehicles']:
            vehicle.upcoming_reservations = models.Reservation.objects.filter(
                vehicle=vehicle,
                end_date__gte=today,
            ).order_by('start_date')
        return context


class ReserveCarView(CreateView):
    model = models.Reservation
    form_class = forms.ReservationForm
    template_name = 'reserve_form.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['vehicle'] = models.Vehicle.objects.get(pk=self.kwargs['vehicle_id'])
        return context

    def form_valid(self, form):
        vehicle = models.Vehicle.objects.get(pk=self.kwargs['vehicle_id'])
        start = form.cleaned_data['start_date']
        end = form.cleaned_data['end_date']

        if end < start:
            form.add_error('end_date', 'End date must be on or after the start date.')
            return self.form_invalid(form)

        overlapping = models.Reservation.objects.filter(
            vehicle=vehicle,
            start_date__lte=end,
            end_date__gte=start,
        ).exists()

        if overlapping:
            form.add_error(None, 'This car is already reserved for part of that range.')
            return self.form_invalid(form)

        form.instance.vehicle = vehicle
        return super().form_valid(form)