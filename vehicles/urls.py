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
    path('return/<int:pk>/', views.ReturnCarView.as_view(), name='return_car'),

    # Reserve
    path('reserve/', views.ReserveCarListView.as_view(), name='reserve_list'),
    path('reserve/<int:vehicle_id>/', views.ReserveCarView.as_view(), name='reserve_car'),
]