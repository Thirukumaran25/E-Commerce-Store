from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    # Storefront/Product Views
    path('', views.product_list, name='product_list'),
    path('category/<slug:category_slug>/', views.product_list, name='product_list_by_category'),
    path('<int:id>/<slug:slug>/', views.product_detail, name='product_detail'),

    # Cart
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),

    # Checkout & Payment
    path('checkout/', views.checkout, name='checkout'),
    path('payment/mock/<int:order_id>/', views.mock_payment, name='mock_payment'),
    path('payment/success/<int:order_id>/', views.payment_success, name='payment_success'),
    # Invoice
    path('order/<int:order_id>/invoice/download/', views.invoice_download, name='invoice_download'),
]
