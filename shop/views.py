from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponse, JsonResponse
import razorpay
import json
import io 

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from .models import Category, Product, Order, OrderItem
from .forms import CartAddProductForm, CheckoutForm


RAZORPAY_CLIENT = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if not cart:
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart

    def add(self, product, quantity=1, update_quantity=False):
        product_id = str(product.id)
        if product_id not in self.cart:
            self.cart[product_id] = {'quantity': 0, 'price': str(product.price)}
        
        if update_quantity:
            self.cart[product_id]['quantity'] = quantity
        else:
            self.cart[product_id]['quantity'] += quantity
        self.save()

    def remove(self, product):
        product_id = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def __iter__(self):
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        for product in products:
            self.cart[str(product.id)]['product'] = product

        for item in self.cart.values():
            item['price'] = float(item['price'])
            item['total_price'] = item['price'] * item['quantity']
            yield item

    def get_total_price(self):
        return sum(float(item['price']) * item['quantity'] for item in self.cart.values())

    def clear(self):
        del self.session[settings.CART_SESSION_ID]
        self.save()

    def save(self):
        self.session.modified = True

# ----------------------------------------------------
# --- Storefront Views ---
# ----------------------------------------------------

def product_list(request, category_slug=None):
    category = None
    categories = Category.objects.all()
    products = Product.objects.filter(available=True)
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
    return render(request, 'shop/product_list.html', {
        'category': category,
        'categories': categories,
        'products': products
    })

def product_detail(request, id, slug):
    product = get_object_or_404(Product, id=id, slug=slug, available=True)
    cart_product_form = CartAddProductForm()
    return render(request, 'shop/product_detail.html', {
        'product': product,
        'cart_product_form': cart_product_form
    })

@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    form = CartAddProductForm(request.POST)

    if form.is_valid():
        cd = form.cleaned_data
        cart.add(product=product, quantity=cd['quantity'], update_quantity=cd['update'])
        messages.success(request, f"{product.name} quantity updated in cart.")
    return redirect('shop:cart_detail')

def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    messages.warning(request, f"{product.name} removed from cart.")
    return redirect('shop:cart_detail')

def cart_detail(request):
    cart = Cart(request)
    for item in cart:
        item['update_quantity_form'] = CartAddProductForm(
            initial={'quantity': item['quantity'], 'update': True}
        )
    return render(request, 'shop/cart_detail.html', {'cart': cart})

# ----------------------------------------------------
# --- Checkout and Payment Logic ---
# ----------------------------------------------------

def checkout(request):
    cart = Cart(request)
    if not cart.get_total_price():
        messages.error(request, "Your cart is empty.")
        return redirect('shop:product_list')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            if request.user.is_authenticated:
                order.user = request.user
            order.save()

            # Create OrderItems
            for item in cart:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    price=item['price'],
                    quantity=item['quantity']
                )

            amount = int(order.get_total_cost() * 100)
            razorpay_order = RAZORPAY_CLIENT.order.create({
                'amount': amount,
                'currency': 'INR',
                'payment_capture': '1'
            })
            
            order.razorpay_order_id = razorpay_order['id']
            order.save()
            
            return JsonResponse({
                'razorpay_order_id': razorpay_order['id'],
                'amount': amount,
                'razorpay_key_id': settings.RAZORPAY_KEY_ID, 
                'message': 'Order initiated'
            })
        else:
            return JsonResponse({'form_errors': form.errors}, status=400)
    else:
        initial_data = {}
        if request.user.is_authenticated:
            initial_data = {
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
            }
        form = CheckoutForm(initial=initial_data)

    return render(request, 'shop/checkout.html', {
        'form': form,
        'cart': cart,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID
    })


@require_POST
def payment_verify(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_signature = data.get('razorpay_signature')
        
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        
        RAZORPAY_CLIENT.utility.verify_payment_signature(params_dict)

        order = get_object_or_404(Order, razorpay_order_id=razorpay_order_id)
        order.paid = True
        order.razorpay_payment_id = razorpay_payment_id
        order.razorpay_signature = razorpay_signature
        order.save()
        
        Cart(request).clear()

        return JsonResponse({
            'status': 'success',
            'redirect_url': redirect('shop:payment_success', order_id=order.id).url
        })

    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({'status': 'failure', 'message': 'Payment verification failed (Signature mismatch).'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'An internal error occurred: {str(e)}'}, status=500)


def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, paid=True)
    return render(request, 'shop/payment_success.html', {'order': order})


# ----------------------------------------------------
# --- Invoice Logic (ReportLab) ---
# ----------------------------------------------------

def generate_reportlab_pdf(order):
    """Generates a PDF invoice using ReportLab."""
    buffer = io.BytesIO()
    
    # Create the PDF object
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                            title=f"Invoice {order.id}",
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # 1. Header and Basic Details
    elements.append(Paragraph("<b>Tax Invoice</b>", styles['Title']))
    elements.append(Paragraph(f"My E-Commerce Store | GSTIN: XXXXXXXXXXXXXX", styles['Normal']))
    elements.append(Spacer(1, 0.25 * inch))

    # 2. Billing/Shipping Details Table
    billing_data = [
        ["Invoice No:", f"INV-{order.id}"],
        ["Invoice Date:", order.created.strftime('%b %d, %Y')],
        ["Payment ID:", order.razorpay_payment_id or "N/A"],
    ]
    billing_table = Table(billing_data, colWidths=[1.5 * inch, 3.5 * inch])
    billing_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    address_data = [
        [Paragraph("<b>Billed To:</b>", styles['Normal'])],
        [order.first_name + " " + order.last_name],
        [order.address],
        [f"{order.city}, {order.postal_code}"],
    ]
    address_table = Table(address_data, colWidths=[2.5 * inch])
    address_table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    # Combine billing and address tables
    header_table = Table([[billing_table, address_table]])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.25 * inch))

    # 3. Items Table
    data = [['Description', 'Unit Price', 'Qty', 'Pre-Tax Total']]
    for item in order.items.all():
        data.append([
            item.product.name,
            f"₹ {item.price:,.2f}",
            str(item.quantity),
            f"₹ {item.get_cost():,.2f}"
        ])

    item_table = Table(data, colWidths=[3 * inch, 1.2 * inch, 0.8 * inch, 1.5 * inch])
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(item_table)
    elements.append(Spacer(1, 0.25 * inch))

    # 4. Footer Summary
    summary_data = [
        ['Subtotal:', f"₹ {order.get_total_cost_before_tax():,.2f}"],
        [f"GST ({order.gst_rate}%)", f"₹ {order.get_gst_amount():,.2f}"],
        ['GRAND TOTAL:', f"₹ {order.get_total_cost():,.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[1.5 * inch, 1.5 * inch])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('LINEBELOW', (0, 0), (-1, -2), 1, colors.black),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 2), (-1, 2), 12),
        ('TEXTCOLOR', (1, 2), (1, 2), colors.darkgreen),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    # Place summary table on the right
    elements.append(Table([['', summary_table]], colWidths=[4.5 * inch, 3 * inch]))

    # Build the PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


def invoice_download(request, order_id):
    order = get_object_or_404(Order, id=order_id, paid=True)

    # Use ReportLab function to generate the PDF buffer
    pdf_buffer = generate_reportlab_pdf(order)

    response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
    filename = f"invoice_{order.id}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response