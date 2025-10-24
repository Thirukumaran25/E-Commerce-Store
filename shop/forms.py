from django import forms
from .models import Order, Product

PRODUCT_QUANTITY_CHOICES = [(i, str(i)) for i in range(1, 21)]

class CartAddProductForm(forms.Form):
    # Form used on the Product Detail page
    quantity = forms.TypedChoiceField(
        choices=PRODUCT_QUANTITY_CHOICES,
        coerce=int,
        widget=forms.Select(attrs={'class': 'w-full p-2 border rounded-md'})
    )
    update = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput)

class CheckoutForm(forms.ModelForm):
    # Form used on the Checkout page
    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'email', 'address', 'city', 'postal_code']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500', 'placeholder': 'Email'}),
            'address': forms.TextInput(attrs={'class': 'w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500', 'placeholder': 'Street Address'}),
            'city': forms.TextInput(attrs={'class': 'w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500', 'placeholder': 'City'}),
            'postal_code': forms.TextInput(attrs={'class': 'w-full p-3 border border-gray-300 rounded-md focus:ring-blue-500', 'placeholder': 'Postal Code'}),
        }