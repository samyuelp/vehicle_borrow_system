from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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
    fuel_percent = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    current_mileage = models.IntegerField(blank=True, null=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.vehicle.car_name} — {self.borrowers_name}"


class Reservation(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    borrowers_name = models.CharField(max_length=200)
    destination = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.vehicle.car_name} — {self.borrowers_name} ({self.start_date} → {self.end_date})"