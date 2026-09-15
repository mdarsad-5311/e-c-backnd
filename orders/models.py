import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class Order(models.Model):
    """
    Model representing a customer order created from a shopping cart checkout.
    Preserves immutable price calculations, totals, and shipping address snapshots.
    """

    class OrderStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    order_number = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Unique public order reference number (e.g. ORD-12345)",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
        db_index=True,
        help_text="Authenticated customer who placed this order",
    )
    status = models.CharField(
        max_length=32,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
        help_text="Current processing status of the order",
    )

    # Server-calculated monetary fields using Decimal (never floats)
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Sum of all order item subtotals",
    )
    shipping_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Shipping and handling charges",
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Calculated tax amount",
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Grand total payable (subtotal + shipping + tax)",
    )

    # Payment information
    payment_method = models.CharField(
        max_length=64,
        blank=True,
        default="Credit Card",
        help_text="Selected payment method (e.g. card, cod, Apple Pay)",
    )
    payment_status = models.CharField(
        max_length=32,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        help_text="Payment state for this order",
    )

    # Shipping & Tracking
    tracking_number = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Carrier shipment tracking identifier",
    )
    estimated_delivery = models.DateField(
        null=True,
        blank=True,
        help_text="Estimated delivery date for shipment",
    )

    # Immutable Shipping Address Snapshot
    shipping_full_name = models.CharField(
        max_length=255,
        help_text="Recipient full name captured at checkout",
    )
    shipping_phone = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Recipient phone number captured at checkout",
    )
    shipping_address_line1 = models.CharField(
        max_length=255,
        help_text="Street address line 1 captured at checkout",
    )
    shipping_address_line2 = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Apartment, suite, unit, etc. captured at checkout",
    )
    shipping_city = models.CharField(
        max_length=100,
        help_text="City captured at checkout",
    )
    shipping_state = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="State / Province captured at checkout",
    )
    shipping_postal_code = models.CharField(
        max_length=30,
        help_text="Postal / ZIP code captured at checkout",
    )
    shipping_country = models.CharField(
        max_length=100,
        default="United States",
        help_text="Country captured at checkout",
    )

    notes = models.TextField(
        blank=True,
        default="",
        help_text="Optional customer order instructions or delivery notes",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return f"{self.order_number} ({self.user.username}) - ${self.total_amount}"

    @property
    def items_count(self) -> int:
        """Distinct order items count"""
        return self.items.count()

    @property
    def total_quantity(self) -> int:
        """Total product units in order"""
        return sum(item.quantity for item in self.items.all())

    @property
    def formatted_address(self) -> str:
        """Formatted single-line address string"""
        parts = [
            self.shipping_address_line1,
            self.shipping_address_line2,
            self.shipping_city,
            f"{self.shipping_state} {self.shipping_postal_code}".strip(),
            self.shipping_country,
        ]
        return ", ".join(p for p in parts if p)

    @property
    def shipping_address_dict(self) -> dict:
        """Structured address dictionary snapshot matching frontend schemas"""
        city_state_zip = f"{self.shipping_city}, {self.shipping_state} {self.shipping_postal_code}".strip().strip(",")
        return {
            "name": self.shipping_full_name,
            "line1": self.shipping_address_line1,
            "line2": self.shipping_address_line2,
            "city": self.shipping_city,
            "state": self.shipping_state,
            "postal_code": self.shipping_postal_code,
            "cityStateZip": city_state_zip or f"{self.shipping_city} {self.shipping_postal_code}".strip(),
            "country": self.shipping_country,
            "phone": self.shipping_phone,
        }

    def generate_order_number(self) -> str:
        """Generate a random unique ORD reference"""
        unique_suffix = uuid.uuid4().hex[:6].upper()
        return f"ORD-{unique_suffix}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            num = self.generate_order_number()
            while Order.objects.filter(order_number=num).exists():
                num = self.generate_order_number()
            self.order_number = num

        if not self.tracking_number:
            self.tracking_number = f"TRK-{uuid.uuid4().hex[:8].upper()}"

        if not self.estimated_delivery:
            self.estimated_delivery = timezone.now().date() + timezone.timedelta(days=3)

        super().save(*args, **kwargs)


class OrderItem(models.Model):
    """
    Model representing an individual item within an Order.
    Stores immutable snapshots of the product details and price at time of purchase.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Order this item belongs to",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        help_text="Reference to original product catalog entry (nullable if product deleted)",
    )

    # Immutable historical snapshots
    product_name = models.CharField(
        max_length=255,
        help_text="Product title / name snapshot at time of purchase",
    )
    product_sku = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Product SKU snapshot",
    )
    product_image_url = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Product primary image URL snapshot",
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per single unit snapshot at time of checkout",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        help_text="Purchased quantity",
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Item total price (unit_price * quantity)",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self):
        return f"{self.quantity}x {self.product_name} (${self.subtotal})"

    @property
    def title(self) -> str:
        """Frontend alias for product_name"""
        return self.product_name

    @property
    def price(self) -> Decimal:
        """Frontend alias for unit_price"""
        return self.unit_price

    @property
    def image(self) -> str:
        """Frontend alias for product_image_url"""
        return self.product_image_url

    @property
    def qty(self) -> int:
        """Frontend alias for quantity"""
        return self.quantity

    def save(self, *args, **kwargs):
        if self.unit_price is not None and self.quantity is not None:
            self.subtotal = Decimal(self.unit_price * self.quantity).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)
