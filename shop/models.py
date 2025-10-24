from django.db import models
from django.db.models import Index # <-- REQUIRED for the 'indexes' Meta option
from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=200, unique=True)

    class Meta:
        ordering = ('name',)
        verbose_name = 'category'
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    available = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    # image field logic omitted for brevity, but a CharField for path is typical

    class Meta:
        ordering = ('name',)
        # FIX: Replaced index_together with indexes list for Django 4.0+ compatibility
        indexes = [
            Index(fields=['id', 'slug']), 
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('shop:product_detail', args=[self.id, self.slug])


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()
    address = models.CharField(max_length=250)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    
    # Payment and Order Details
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=250, blank=True, null=True)
    paid = models.BooleanField(default=False)
    
    # Invoice and Tax
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00) # Example 18%
    
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        return f'Order {self.id}'

    def get_total_cost_before_tax(self):
        return sum(item.get_cost() for item in self.items.all())

    def get_gst_amount(self):
        total_before_tax = self.get_total_cost_before_tax()
        return round(total_before_tax * (self.gst_rate / 100), 2)

    def get_total_cost(self):
        return self.get_total_cost_before_tax() + self.get_gst_amount()


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='order_items', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return str(self.id)

    def get_cost(self):
        return self.price * self.quantity