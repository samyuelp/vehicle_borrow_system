import random

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def _generate_code():
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=4))


class Vehicle(models.Model):
    car_name = models.CharField(max_length=200)

    def __str__(self):
        return self.car_name


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
        # Is there an unreturned borrow linked to this reservation?
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