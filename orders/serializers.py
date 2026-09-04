from decimal import Decimal
from rest_framework import serializers

from accounts.models import Address
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer for OrderItem representation including frontend alias fields.
    """
    title = serializers.CharField(source="product_name", read_only=True)
    price = serializers.DecimalField(source="unit_price", max_digits=10, decimal_places=2, read_only=True)
    qty = serializers.IntegerField(source="quantity", read_only=True)
    image = serializers.CharField(source="product_image_url", read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(source="product", read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_id",
            "product_name",
            "title",
            "product_sku",
            "product_image_url",
            "image",
            "unit_price",
            "price",
            "quantity",
            "qty",
            "subtotal",
            "created_at",
        ]
        read_only_fields = fields


class InlineShippingAddressSerializer(serializers.Serializer):
    """
    Serializer for validating an inline shipping address submitted during checkout.
    """
    full_name = serializers.CharField(required=False, max_length=255)
    name = serializers.CharField(required=False, max_length=255)
    phone_number = serializers.CharField(required=False, max_length=50, allow_blank=True)
    phone = serializers.CharField(required=False, max_length=50, allow_blank=True)
    street_address = serializers.CharField(required=False, max_length=255)
    line1 = serializers.CharField(required=False, max_length=255)
    line2 = serializers.CharField(required=False, max_length=255, allow_blank=True, default="")
    city = serializers.CharField(required=False, max_length=100)
    state = serializers.CharField(required=False, max_length=100, allow_blank=True, default="")
    postal_code = serializers.CharField(required=False, max_length=30)
    cityStateZip = serializers.CharField(required=False, max_length=255, allow_blank=True)
    country = serializers.CharField(required=False, max_length=100, default="United States")

    def validate(self, attrs):
        name = attrs.get("full_name") or attrs.get("name")
        line1 = attrs.get("street_address") or attrs.get("line1")
        phone = attrs.get("phone_number") or attrs.get("phone") or ""
        city = attrs.get("city")
        postal_code = attrs.get("postal_code")
        city_state_zip = attrs.get("cityStateZip")

        if not name or len(name.strip()) < 2:
            raise serializers.ValidationError({"name": "Full name is required (at least 2 characters)."})

        if not line1 or len(line1.strip()) < 5:
            raise serializers.ValidationError({"line1": "Street address is required (at least 5 characters)."})

        # If combined cityStateZip provided without separate city/postal_code, parse loosely or accept
        if not city and not city_state_zip:
            raise serializers.ValidationError({"city": "City or City/State/ZIP is required."})

        return attrs


class OrderCreateSerializer(serializers.Serializer):
    """
    Serializer for validating order creation at checkout.
    Takes either an existing saved address ID or an inline address payload.
    """
    shipping_address_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID of an existing saved User Address",
    )
    shipping_address = InlineShippingAddressSerializer(
        required=False,
        allow_null=True,
        help_text="Inline delivery address object if not using a saved address",
    )
    payment_method = serializers.CharField(
        required=False,
        default="Credit Card",
        max_length=64,
        help_text="Payment method (e.g., card, cod, Apple Pay)",
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional customer order instructions",
    )

    def validate_shipping_address_id(self, value):
        if value:
            request = self.context.get("request")
            if not request or not request.user or not request.user.is_authenticated:
                raise serializers.ValidationError("User authentication required.")
            if not Address.objects.filter(id=value, user=request.user).exists():
                raise serializers.ValidationError("Address not found or does not belong to the current user.")
        return value

    def validate(self, attrs):
        addr_id = attrs.get("shipping_address_id")
        inline_addr = attrs.get("shipping_address")

        if not addr_id and not inline_addr:
            raise serializers.ValidationError(
                {"shipping_address": "Either shipping_address_id or shipping_address details must be provided."}
            )

        return attrs


class OrderListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing user orders with full summary data and frontend aliases.
    """
    items = OrderItemSerializer(many=True, read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    itemsCount = serializers.IntegerField(source="items_count", read_only=True)
    total_quantity = serializers.IntegerField(read_only=True)
    totalAmount = serializers.DecimalField(source="total_amount", max_digits=12, decimal_places=2, read_only=True)
    date = serializers.DateTimeField(source="created_at", format="%Y-%m-%d", read_only=True)
    placed = serializers.DateTimeField(source="created_at", format="%B %d, %Y", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    trackingNumber = serializers.CharField(source="tracking_number", read_only=True)
    estimatedDelivery = serializers.DateField(source="estimated_delivery", read_only=True)
    shippingAddress = serializers.CharField(source="formatted_address", read_only=True)
    paymentMethod = serializers.CharField(source="payment_method", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "status_display",
            "subtotal",
            "shipping_cost",
            "tax_amount",
            "total_amount",
            "totalAmount",
            "payment_method",
            "paymentMethod",
            "payment_status",
            "tracking_number",
            "trackingNumber",
            "estimated_delivery",
            "estimatedDelivery",
            "shippingAddress",
            "items_count",
            "itemsCount",
            "total_quantity",
            "items",
            "created_at",
            "date",
            "placed",
            "updated_at",
        ]
        read_only_fields = fields


class OrderDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for single order detail view.
    """
    items = OrderItemSerializer(many=True, read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    itemsCount = serializers.IntegerField(source="items_count", read_only=True)
    total_quantity = serializers.IntegerField(read_only=True)
    totalAmount = serializers.DecimalField(source="total_amount", max_digits=12, decimal_places=2, read_only=True)
    date = serializers.DateTimeField(source="created_at", format="%Y-%m-%d", read_only=True)
    placed = serializers.DateTimeField(source="created_at", format="%B %d, %Y", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    trackingNumber = serializers.CharField(source="tracking_number", read_only=True)
    estimatedDelivery = serializers.DateField(source="estimated_delivery", read_only=True)
    shipping_address = serializers.DictField(source="shipping_address_dict", read_only=True)
    shippingAddress = serializers.CharField(source="formatted_address", read_only=True)
    paymentMethod = serializers.CharField(source="payment_method", read_only=True)
    summary = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "status_display",
            "subtotal",
            "shipping_cost",
            "tax_amount",
            "total_amount",
            "totalAmount",
            "summary",
            "payment_method",
            "paymentMethod",
            "payment_status",
            "tracking_number",
            "trackingNumber",
            "estimated_delivery",
            "estimatedDelivery",
            "shipping_address",
            "shippingAddress",
            "notes",
            "items_count",
            "itemsCount",
            "total_quantity",
            "items",
            "timeline",
            "created_at",
            "date",
            "placed",
            "updated_at",
        ]
        read_only_fields = fields

    def get_summary(self, obj: Order) -> dict:
        return {
            "subtotal": float(obj.subtotal),
            "shipping": float(obj.shipping_cost),
            "tax": float(obj.tax_amount),
            "total": float(obj.total_amount),
        }

    def get_timeline(self, obj: Order) -> list:
        current_status = obj.status.lower()
        status_order = ["pending", "confirmed", "processing", "shipped", "delivered"]

        try:
            current_index = status_order.index(current_status)
        except ValueError:
            current_index = -1

        steps = [
            {"id": "ordered", "label": "Order Placed", "status_key": "pending"},
            {"id": "confirmed", "label": "Order Confirmed", "status_key": "confirmed"},
            {"id": "processing", "label": "Processing", "status_key": "processing"},
            {"id": "shipped", "label": "Shipped", "status_key": "shipped"},
            {"id": "delivered", "label": "Delivered", "status_key": "delivered"},
        ]

        timeline = []
        for idx, step in enumerate(steps):
            is_done = current_index >= idx and current_status != "cancelled"
            is_active = current_index == idx and current_status != "cancelled"
            timeline.append({
                "id": step["id"],
                "label": step["label"],
                "detail": obj.created_at.strftime("%b %d, %I:%M %p") if (idx == 0 and is_done) else "",
                "done": is_done,
                "active": is_active,
            })

        if current_status == "cancelled":
            timeline.append({
                "id": "cancelled",
                "label": "Order Cancelled",
                "detail": obj.updated_at.strftime("%b %d, %I:%M %p"),
                "done": True,
                "active": True,
            })

        return timeline


class OrderStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for admin order status updates.
    """
    status = serializers.ChoiceField(choices=Order.OrderStatus.choices, required=True)
    tracking_number = serializers.CharField(required=False, allow_blank=True, max_length=64)
    notes = serializers.CharField(required=False, allow_blank=True)
