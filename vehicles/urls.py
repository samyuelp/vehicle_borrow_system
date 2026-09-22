from django.urls import path

from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),

    # Borrow
    path('borrow/', views.AvailableCarListView.as_view(), name='borrow_list'),
    path('borrow/<int:vehicle_id>/', views.BorrowCarView.as_view(), name='borrow_car'),

    # Return
    path('return/', views.BorrowedCarListView.as_view(), name='return_list'),
    path('return/<int:pk>/confirm/', views.ConfirmBorrowerView.as_view(), name='return_confirm'),
    path('return/<int:pk>/reservation/', views.ReturnReservationChoiceView.as_view(), name='return_reservation_choice'),
    path('return/<int:pk>/reservation/cancel/', views.ReturnReservationCancelView.as_view(), name='return_reservation_cancel'),
    path('return/<int:pk>/reservation/keep/', views.ReturnReservationKeepView.as_view(), name='return_reservation_keep'),
    path('return/<int:pk>/', views.ReturnCarView.as_view(), name='return_car'),

    # Reserve
    path('reserve/', views.ReserveCarListView.as_view(), name='reserve_list'),
    path('reserve/<int:vehicle_id>/', views.ReserveCarView.as_view(), name='reserve_car'),
    path('reserve/success/<int:pk>/', views.ReserveSuccessView.as_view(), name='reserve_success'),

    # Pickup
    path('pickup/<int:reservation_id>/', views.PickupView.as_view(), name='pickup'),
]