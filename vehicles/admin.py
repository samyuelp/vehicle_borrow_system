from django.contrib import admin

from .models import Vehicle, BorrowDetail, Reservation


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('car_name',)
    search_fields = ('car_name',)


@admin.register(BorrowDetail)
class BorrowDetailAdmin(admin.ModelAdmin):
    list_display = (
        'vehicle',
        'borrowers_name',
        'destination',
        'borrow_time',
        'actual_return_time',
        'fuel_percent',
        'current_mileage',
    )
    list_filter = ('vehicle', 'borrow_time', 'actual_return_time')
    search_fields = ('borrowers_name', 'destination', 'notes')
    date_hierarchy = 'borrow_time'
    ordering = ('-borrow_time',)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        'vehicle',
        'borrowers_name',
        'destination',
        'start_date',
        'end_date',
    )
    list_filter = ('vehicle', 'start_date', 'end_date')
    search_fields = ('borrowers_name', 'destination', 'notes')
    ordering = ('start_date',)