from django.urls import path
from . import views

urlpatterns = [
    # 1. Home
    path('', views.HomeView.as_view(), name='home'),

    # Borrow flow
    path('borrow/', views.AvailableCarListView.as_view(), name='borrow_list'),
    path('borrow/<int:vehicle_id>/', views.BorrowCarView.as_view(), name='borrow_car'),

    # Return flow
    path('return/', views.BorrowedCarListView.as_view(), name='return_list'),
    path('return/<int:pk>/confirm/', views.ConfirmBorrowerView.as_view(), name='return_confirm'),
    path('return/<int:pk>/', views.ReturnCarView.as_view(), name='return_car'),
]