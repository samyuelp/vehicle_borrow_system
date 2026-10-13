import random

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def _generate_code():
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=4))


class Vehicle(models.Model):
    car_name = models.CharField(max_length=200)
    next_service_date = models.DateField(
        blank=True,
        null=True,
        help_text='Date the next service is due. Leave blank if not tracked.',
    )
    next_service_mileage = models.IntegerField(
        blank=True,
        null=True,
        help_text='Mileage at which the next service is due. Leave blank if not tracked.',
    )

    def __str__(self):
        return self.car_name

    @property
    def last_known_mileage(self):
        """Highest mileage recorded on any returned borrow for this vehicle."""
        result = self.borrowdetail_set.filter(
            actual_return_time__isnull=False,
            current_mileage__isnull=False,
        ).aggregate(models.Max('current_mileage'))
        return result['current_mileage__max']

    @property
    def last_known_fuel(self):
        """Fuel percent recorded on the most recent return for this vehicle."""
        latest = self.borrowdetail_set.filter(
            actual_return_time__isnull=False,
            fuel_percent__isnull=False,
        ).order_by('-actual_return_time').first()
        return latest.fuel_percent if latest else None

    @property
    def service_status(self):
        """Warn-only service status.

        Returns a dict:
            due (bool)      -- service is past due (date or mileage)
            soon (bool)     -- service is approaching (date only)
            reasons (list)  -- e.g. ['Date', 'Mileage']
        """
        today = timezone.localdate()
        due_reasons = []

        # Date check
        date_due = False
        date_soon = False
        if self.next_service_date is not None:
            days_until = (self.next_service_date - today).days
            if days_until < 0:
                date_due = True
                due_reasons.append('Date')
            elif days_until <= 14:
                date_soon = True

        # Mileage check
        mileage_due = False
        if self.next_service_mileage is not None:
            mileage = self.last_known_mileage
            if mileage is not None and mileage >= self.next_service_mileage:
                mileage_due = True
                due_reasons.append('Mileage')

        return {
            'due': date_due or mileage_due,
            'soon': date_soon and not (date_due or mileage_due),
            'reasons': due_reasons,
        }


class BorrowDetail(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    borrowers_name = models.CharField(max_length=200)
    destination = models.TextField()
    borrow_time = models.DateTimeField(auto_now_add=True)
    actual_return_time = models.DateTimeField(blank=True, null=True)
    expected_return_date = models.DateField(blank=True, null=True)
    reservation = models.ForeignKey(
        'Reservation',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='borrows',
    )
    fuel_percent = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    current_mileage = models.IntegerField(blank=True, null=True)
    notes = models.TextField(blank=True, default='')

    @property
    def is_overdue(self):
        """A borrow is overdue if it has an expected return date that's passed
        and the car hasn't been returned yet."""
        if self.actual_return_time is not None:
            return False
        if self.expected_return_date is None:
            return False
        return self.expected_return_date < timezone.localdate()

    def __str__(self):
        return f"{self.vehicle.car_name} — {self.borrowers_name}"


class Reservation(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    borrowers_name = models.CharField(max_length=200)
    destination = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    code = models.CharField(max_length=6, unique=True, blank=True)
    fulfilled = models.BooleanField(default=False)
    cancelled = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')

    @property
    def is_active(self):
        """Active = not cancelled, not fulfilled, and today is within the window."""
        if self.cancelled or self.fulfilled:
            return False
        today = timezone.localdate()
        return self.start_date <= today <= self.end_date

    @property
    def is_overdue(self):
        """Overdue = window has ended, but the linked borrow hasn't been returned."""
        today = timezone.localdate()
        if self.cancelled or self.fulfilled:
            return False
        if today <= self.end_date:
            return False
        return self.borrows.filter(actual_return_time__isnull=True).exists()

    def save(self, *args, **kwargs):
        if not self.code:
            while True:
                code = _generate_code()
                if not Reservation.objects.filter(code=code).exists():
                    self.code = code
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.vehicle.car_name} — {self.borrowers_name} ({self.start_date} → {self.end_date})"