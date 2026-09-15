from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django.db.models import F
import logging

logger = logging.getLogger('django')

from accounts.models import Address
from cart.models import Cart
from products.models import Product
from .models import Order, OrderItem
from .serializers import (
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    OrderStatusUpdateSerializer,
)
from .permissions import IsOrderOwner


class OrderViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for customer Order placement, order history, order details,
    cancellations, and admin status fulfillment management.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ["update", "partial_update", "status_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Order deletion is not allowed."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def get_throttles(self):
        if self.action == 'create':
            self.throttle_scope = 'checkout'
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Order.objects.none()

        qs = (
            Order.objects.prefetch_related("items__product", "items__product__images")
            .select_related("user")
            .all()
        )

        # Non-staff users only see their own orders (strict IDOR protection)
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)

        # Status filtering support for admin and users (e.g. ?status=processing)
        status_param = self.request.query_params.get("status")
        if status_param and status_param.upper() != "ALL":
            qs = qs.filter(status__iexact=status_param.strip().lower())

        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        elif self.action in ["retrieve", "cancel"]:
            return OrderDetailSerializer
        elif self.action in ["update", "partial_update", "status_update"]:
            return OrderStatusUpdateSerializer
        return OrderListSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new order atomically from the authenticated user's current Cart.
        Strictly computes prices and updates product stocks server-side.
        """
        serializer = OrderCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        user = request.user

        # Run checkout in an atomic transaction to ensure data integrity
        with transaction.atomic():
            # 1. Fetch user's cart
            try:
                cart = Cart.objects.select_for_update().get(user=user)
            except Cart.DoesNotExist:
                return Response(
                    {"detail": "Your shopping cart is empty."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            cart_items = list(
                cart.items.select_related("product", "product__category")
                .prefetch_related("product__images")
                .all()
            )

            if not cart_items:
                return Response(
                    {"detail": "Your shopping cart is empty."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 2. Validate product availability and inventory
            for item in cart_items:
                product = item.product
                if not product or not product.is_active or (product.category and not product.category.is_active):
                    return Response(
                        {"detail": f"Product '{product.name if product else 'Unknown'}' is currently unavailable."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if item.quantity < 1:
                    return Response(
                        {"detail": f"Invalid quantity for '{product.name}'."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if product.stock < item.quantity:
                    return Response(
                        {
                            "detail": f"Insufficient stock for '{product.name}'. Only {product.stock} available in stock."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # 3. Resolve Shipping Address snapshot
            shipping_addr_id = validated_data.get("shipping_address_id")
            inline_addr = validated_data.get("shipping_address")

            if shipping_addr_id:
                addr = Address.objects.get(id=shipping_addr_id, user=user)
                full_name = addr.full_name
                phone = addr.phone_number or ""
                line1 = addr.street_address
                line2 = ""
                city = addr.city
                state = addr.state or ""
                postal_code = addr.postal_code
                country = addr.country or "United States"
            else:
                full_name = (inline_addr.get("full_name") or inline_addr.get("name") or "").strip()
                phone = (inline_addr.get("phone_number") or inline_addr.get("phone") or "").strip()
                line1 = (inline_addr.get("street_address") or inline_addr.get("line1") or "").strip()
                line2 = (inline_addr.get("line2") or "").strip()
                city = (inline_addr.get("city") or "").strip()
                state = (inline_addr.get("state") or "").strip()
                postal_code = (inline_addr.get("postal_code") or "").strip()
                country = (inline_addr.get("country") or "United States").strip()

                # Parse cityStateZip fallback if city / postal_code were passed as unified string
                city_state_zip = inline_addr.get("cityStateZip", "")
                if city_state_zip and (not city or not postal_code):
                    if not city:
                        city = city_state_zip.split(",")[0].strip()
                    if not postal_code:
                        postal_code = "00000"

            # 4. Compute prices securely on server (never trust client amounts)
            subtotal = Decimal("0.00")
            for item in cart_items:
                subtotal += Decimal(item.product.price * item.quantity).quantize(Decimal("0.01"))

            shipping_cost = Decimal("0.00")
            tax_amount = Decimal("0.00")
            total_amount = (subtotal + shipping_cost + tax_amount).quantize(Decimal("0.01"))

            payment_method = validated_data.get("payment_method", "Credit Card")
            notes = validated_data.get("notes", "")

            # 5. Create Order record
            order = Order.objects.create(
                user=user,
                status=Order.OrderStatus.PENDING,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                tax_amount=tax_amount,
                total_amount=total_amount,
                payment_method=payment_method,
                payment_status=Order.PaymentStatus.PENDING,
                shipping_full_name=full_name,
                shipping_phone=phone,
                shipping_address_line1=line1,
                shipping_address_line2=line2,
                shipping_city=city,
                shipping_state=state,
                shipping_postal_code=postal_code,
                shipping_country=country,
                notes=notes,
            )

            # 6. Create OrderItems & decrement product stock atomically
            order_items_to_create = []
            for item in cart_items:
                product = item.product
                primary_img = product.primary_image
                image_url = primary_img.image.url if (primary_img and primary_img.image) else ""

                item_subtotal = Decimal(product.price * item.quantity).quantize(Decimal("0.01"))

                order_item = OrderItem(
                    order=order,
                    product=product,
                    product_name=product.name,
                    product_sku=product.sku or "",
                    product_image_url=image_url,
                    unit_price=product.price,
                    quantity=item.quantity,
                    subtotal=item_subtotal,
                )
                order_items_to_create.append(order_item)

                # Decrement inventory stock
                Product.objects.filter(id=product.id).update(stock=F('stock') - item.quantity)

            OrderItem.objects.bulk_create(order_items_to_create)

            # 7. Clear cart items only after successful order and item creation
            cart.items.all().delete()

        # Reload order with relations for serialization
        order = Order.objects.prefetch_related(
            "items__product", "items__product__images"
        ).get(id=order.id)
        
        logger.info(f"Order created successfully: {order.order_number} by {user.username}")
        
        response_serializer = OrderDetailSerializer(order, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """
        Customer endpoint to cancel a pending or processing order and restore stock.
        """
        order = self.get_object()

        # IDOR and status validation
        if order.status in [Order.OrderStatus.SHIPPED, Order.OrderStatus.DELIVERED, Order.OrderStatus.CANCELLED]:
            return Response(
                {"detail": f"Cannot cancel an order with status '{order.get_status_display()}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Restore product inventory
            for item in order.items.all():
                if item.product_id:
                    Product.objects.filter(id=item.product_id).update(stock=F('stock') + item.quantity)

            order.status = Order.OrderStatus.CANCELLED
            order.save(update_fields=["status", "updated_at"])

        serializer = OrderDetailSerializer(order, context={"request": request})
        return Response(
            {
                "detail": "Order cancelled successfully.",
                "order": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def _apply_status_update(self, order, validated_data, request):
        new_status = validated_data.get("status")
        tracking_num = validated_data.get("tracking_number")
        notes = validated_data.get("notes")

        if order.status == Order.OrderStatus.CANCELLED:
            return Response(
                {"detail": "Cancelled orders cannot be modified or processed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status and new_status != order.status:
            if order.status == Order.OrderStatus.DELIVERED:
                return Response(
                    {"detail": "Delivered orders cannot be modified."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            order.status = new_status

        update_fields = ["updated_at"]
        if new_status:
            update_fields.append("status")
        if tracking_num is not None:
            order.tracking_number = tracking_num
            update_fields.append("tracking_number")
        if notes is not None:
            order.notes = notes
            update_fields.append("notes")

        order.save(update_fields=update_fields)
        logger.info(f"Order status updated: {order.order_number} to {order.status}")

        detail_serializer = OrderDetailSerializer(order, context={"request": request})
        return Response(
            {
                "detail": f"Order status updated to '{order.get_status_display()}'.",
                "order": detail_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        order = self.get_object()
        serializer = OrderStatusUpdateSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        return self._apply_status_update(order, serializer.validated_data, request)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(
        detail=True,
        methods=["patch", "put", "post"],
        url_path="status",
        permission_classes=[permissions.IsAdminUser],
    )
    def status_update(self, request, pk=None):
        """
        Admin endpoint to update order status and tracking details.
        """
        order = self.get_object()
        serializer = OrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._apply_status_update(order, serializer.validated_data, request)
