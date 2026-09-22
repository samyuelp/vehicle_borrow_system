from django.contrib import admin
from django.utils import timezone

from .models import Vehicle, BorrowDetail, Reservation


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('car_name', 'current_status')
    search_fields = ('car_name',)

    def current_status(self, obj):
        today = timezone.localdate()

        # Overdue?
        overdue = obj.borrowdetail_set.filter(
            actual_return_time__isnull=True,
            expected_return_date__lt=today,
        ).first()
        if overdue:
            return f"⚠️ Overdue — {overdue.borrowers_name}"

        # Currently out?
        out = obj.borrowdetail_set.filter(
            actual_return_time__isnull=True,
        ).first()
        if out:
            return f"🚗 Out — {out.borrowers_name}"

        # Reserved today?
        reserved = obj.reservation_set.filter(
            cancelled=False,
            fulfilled=False,
            start_date__lte=today,
            end_date__gte=today,
        ).first()
        if reserved:
            return f"📅 Reserved today — {reserved.borrowers_name}"

        # Upcoming reservation?
        upcoming = obj.reservation_set.filter(
            cancelled=False,
            fulfilled=False,
            end_date__gte=today,
        ).order_by('start_date').first()
        if upcoming:
            return f"📅 Next: {upcoming.start_date} → {upcoming.end_date}"

        return "✅ Available"

    current_status.short_description = 'Status'


@admin.register(BorrowDetail)
class BorrowDetailAdmin(admin.ModelAdmin):
    list_display = (
        'vehicle',
        'borrowers_name',
        'destination',
        'borrow_time',
        'expected_return_date',
        'actual_return_time',
        'is_overdue_display',
        'fuel_percent',
        'current_mileage',
        'notes',
    )
    list_filter = ('vehicle', 'borrow_time', 'actual_return_time', 'expected_return_date')
    search_fields = ('borrowers_name', 'destination', 'notes')
    date_hierarchy = 'borrow_time'
    ordering = ('-borrow_time',)

    def is_overdue_display(self, obj):
        return "⚠️ Yes" if obj.is_overdue else "—"
    is_overdue_display.short_description = 'Overdue?'


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        'vehicle',
        'borrowers_name',
        'destination',
        'start_date',
        'end_date',
        'code',
        'status_display',
        'notes',
    )
    list_filter = ('vehicle', 'start_date', 'end_date', 'cancelled', 'fulfilled')
    search_fields = ('borrowers_name', 'destination', 'notes', 'code')
    ordering = ('start_date',)

    def status_display(self, obj):
        if obj.cancelled:
            return "❌ Cancelled"
        if obj.fulfilled:
            return "✔️ Fulfilled"
        if obj.is_overdue:
            return "⚠️ Overdue"
        if obj.is_active:
            return "📅 Active"
        today = timezone.localdate()
        if obj.start_date > today:
            return "🕒 Upcoming"
        return "⌛ Expired"
    status_display.short_description = 'Status'