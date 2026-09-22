from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
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
        cancelled=False,
        fulfilled=False,
        start_date__lte=today,
        end_date__gte=today,
    ).first()

    upcoming_reservation = models.Reservation.objects.filter(
        vehicle=vehicle,
        cancelled=False,
        fulfilled=False,
        end_date__gte=today,
    ).order_by('start_date').first()

    # Overdue: an unreturned borrow whose expected_return_date has passed
    overdue_borrow = models.BorrowDetail.objects.filter(
        vehicle=vehicle,
        actual_return_time__isnull=True,
        expected_return_date__lt=today,
    ).first()

    is_available = (
        not current_borrow
        and not reserved_today
        and not overdue_borrow
    )

    return {
        'current_borrow': current_borrow,
        'reserved_today': reserved_today,
        'upcoming_reservation': upcoming_reservation,
        'overdue_borrow': overdue_borrow,
        'is_available': is_available,
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
        vehicle = get_object_or_404(models.Vehicle, pk=kwargs['vehicle_id'])
        status = _vehicle_status(vehicle)

        if status['overdue_borrow']:
            return render(request, 'borrow_unavailable.html', {
                'vehicle': vehicle,
                'status': status,
                'reason': 'overdue',
            })

        if status['reserved_today']:
            return redirect('pickup', reservation_id=status['reserved_today'].pk)

        if status['current_borrow']:
            return render(request, 'borrow_unavailable.html', {
                'vehicle': vehicle,
                'status': status,
                'reason': 'out',
            })

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['vehicle'] = get_object_or_404(models.Vehicle, pk=self.kwargs['vehicle_id'])
        return context

    def form_valid(self, form):
        vehicle = get_object_or_404(models.Vehicle, pk=self.kwargs['vehicle_id'])
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

    def form_valid(self, form):
        form.instance.actual_return_time = timezone.now()
        response = super().form_valid(form)

        reservation = form.instance.reservation
        if reservation and not reservation.cancelled and not reservation.fulfilled:
            # Returned after the window ended? Mark fulfilled and go home.
            if timezone.localdate() > reservation.end_date:
                reservation.fulfilled = True
                reservation.save()
                return response
            # Returned within the window? Ask cancel-or-keep.
            return redirect('return_reservation_choice', pk=form.instance.pk)

        return response

    def get_success_url(self):
        return reverse_lazy('home')


class ReturnReservationChoiceView(DetailView):
    model = models.BorrowDetail
    template_name = 'return_reservation_choice.html'
    context_object_name = 'borrow'


class ReturnReservationCancelView(DetailView):
    model = models.BorrowDetail

    def get(self, request, *args, **kwargs):
        borrow = self.get_object()
        reservation = borrow.reservation
        if reservation and not reservation.cancelled:
            reservation.cancelled = True
            reservation.save()
        return redirect('home')


class ReturnReservationKeepView(DetailView):
    model = models.BorrowDetail

    def get(self, request, *args, **kwargs):
        # Do nothing — reservation stays active
        return redirect('home')


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
                cancelled=False,
                fulfilled=False,
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
        context['vehicle'] = get_object_or_404(models.Vehicle, pk=self.kwargs['vehicle_id'])
        return context

    def form_valid(self, form):
        vehicle = get_object_or_404(models.Vehicle, pk=self.kwargs['vehicle_id'])
        start = form.cleaned_data['start_date']
        end = form.cleaned_data['end_date']

        if end < start:
            form.add_error('end_date', 'End date must be on or after the start date.')
            return self.form_invalid(form)

        overlapping = models.Reservation.objects.filter(
            vehicle=vehicle,
            cancelled=False,
            fulfilled=False,
            start_date__lte=end,
            end_date__gte=start,
        ).exists()

        if overlapping:
            form.add_error(None, 'This car is already reserved for part of that range.')
            return self.form_invalid(form)

        form.instance.vehicle = vehicle
        super().form_valid(form)
        return redirect('reserve_success', pk=self.object.pk)


class ReserveSuccessView(DetailView):
    model = models.Reservation
    template_name = 'reserve_success.html'
    context_object_name = 'reservation'


# ---------- Pickup flow ----------

class PickupView(FormView):
    template_name = 'pickup.html'
    form_class = forms.PickupCodeForm

    def dispatch(self, request, *args, **kwargs):
        self.reservation = get_object_or_404(models.Reservation, pk=kwargs['reservation_id'])

        if self.reservation.cancelled or self.reservation.fulfilled:
            return redirect('home')

        today = timezone.localdate()
        if not (self.reservation.start_date <= today <= self.reservation.end_date):
            return redirect('home')

        if models.BorrowDetail.objects.filter(
            vehicle=self.reservation.vehicle,
            actual_return_time__isnull=True,
        ).exists():
            return redirect('home')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reservation'] = self.reservation
        return context

    def form_valid(self, form):
        entered = form.cleaned_data['code']
        if entered != self.reservation.code:
            form.add_error('code', 'That code does not match this reservation.')
            return self.form_invalid(form)

        models.BorrowDetail.objects.create(
            vehicle=self.reservation.vehicle,
            borrowers_name=self.reservation.borrowers_name,
            destination=self.reservation.destination,
            expected_return_date=self.reservation.end_date,
            reservation=self.reservation,
        )

        return redirect('home')