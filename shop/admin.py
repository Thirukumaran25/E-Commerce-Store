# shop/admin.py
from django.contrib import admin
from .models import Category, Product, Order, OrderItem

# --- Product Management ---

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # Automatically populate the slug field from the name field
    prepopulated_fields = {'slug': ('name',)}
    list_display = ['name', 'slug']
    ordering = ['name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'price', 'stock', 'available', 'created', 'updated']
    list_filter = ['available', 'created', 'updated', 'category']
    # Automatically populate the slug field from the name field
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['price', 'stock', 'available'] # Allows quick editing from the list view

# --- Order Management (Optional but Recommended) ---

# Inline class to display order items directly within the Order admin page
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    # Prevents adding or deleting items via the inline for completed orders
    readonly_fields = ['price', 'quantity']
    can_delete = False
    max_num = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'first_name', 'last_name', 'email', 'paid', 'get_total_cost', 'created']
    list_filter = ['paid', 'created', 'updated']
    list_display_links = ['id', 'first_name']
    inlines = [OrderItemInline]
    readonly_fields = ['get_total_cost', 'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature']
    
    # Custom method to display total cost in the list/detail view
    def get_total_cost(self, obj):
        return f"₹ {obj.get_total_cost():,.2f}"
    get_total_cost.short_description = 'Total Cost (w/ GST)'