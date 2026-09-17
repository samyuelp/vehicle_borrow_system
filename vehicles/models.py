from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Vehicle(models.Model):
    car_name = models.CharField(max_length=200)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return str(self.car_name)


class BorrowDetail(models.Model):
    car_name = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    borrowers_name = models.CharField(max_length=200)
    destination = models.TextField()
    borrow_time = models.DateTimeField(auto_now_add=True)
    fuel_percent = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    current_mileage = models.IntegerField(blank=True, null=True)
    return_time = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return str(self.car_name)