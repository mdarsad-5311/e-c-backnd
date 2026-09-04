from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Q, UniqueConstraint


class Cart(models.Model):
    """
    Model representing an active shopping cart for an authenticated user.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
        help_text="User who owns this cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Cart"
        verbose_name_plural = "Carts"

    def __str__(self):
        return f"Cart for {self.user.username} ({self.total_items_count} units)"

    @property
    def total_items_count(self):
        """Sum of all item quantities in the cart"""
        return sum(item.quantity for item in self.items.all())

    @property
    def unique_items_count(self):
        """Total number of unique products in the cart"""
        return self.items.count()

    @property
    def subtotal(self):
        """Total selling price for all items in the cart"""
        total = sum(item.subtotal for item in self.items.all())
        return Decimal(total).quantize(Decimal("0.01")) if total else Decimal("0.00")

    @property
    def total_original_price(self):
        """Total compare-at/original price before discounts"""
        total = sum(item.original_price_subtotal for item in self.items.all())
        return Decimal(total).quantize(Decimal("0.01")) if total else Decimal("0.00")

    @property
    def total_savings(self):
        """Total discount savings on all items"""
        savings = self.total_original_price - self.subtotal
        return max(Decimal("0.00"), savings).quantize(Decimal("0.01"))

    @property
    def total(self):
        """Final total price payable"""
        return self.subtotal


class CartItem(models.Model):
    """
    Model representing a specific product and quantity inside a cart.
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Cart this item belongs to"
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="cart_items",
        help_text="Product added to cart"
    )
    quantity = models.PositiveIntegerField(
        default=1,
        help_text="Quantity of product (must be >= 1)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        constraints = [
            UniqueConstraint(fields=["cart", "product"], name="unique_cart_product"),
            CheckConstraint(check=Q(quantity__gt=0), name="cart_item_quantity_positive"),
        ]

    def __str__(self):
        return f"{self.quantity}x {self.product.name} in cart {self.cart.id}"

    @property
    def subtotal(self):
        """Subtotal price for this cart item based on current product price"""
        return Decimal(self.product.price * self.quantity).quantize(Decimal("0.01"))

    @property
    def original_price_subtotal(self):
        """Subtotal original price for this cart item"""
        orig = self.product.compare_at_price or self.product.price
        return Decimal(orig * self.quantity).quantize(Decimal("0.01"))
