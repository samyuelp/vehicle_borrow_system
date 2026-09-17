from django.contrib import admin
from .models import Vehicle, BorrowDetail


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('car_name', 'is_available')
    list_filter = ('is_available',)
    search_fields = ('car_name',)


@admin.register(BorrowDetail)
class BorrowDetailAdmin(admin.ModelAdmin):
    list_display = (
        'car_name',
        'borrowers_name',
        'destination',
        'borrow_time',
        'return_time',
        'fuel_percent',
        'current_mileage',
    )
    list_filter = ('car_name', 'borrow_time', 'return_time')
    search_fields = ('borrowers_name', 'destination')
    date_hierarchy = 'borrow_time'
    ordering = ('-borrow_time',)