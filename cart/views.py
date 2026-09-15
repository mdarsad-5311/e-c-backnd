from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product
from .models import Cart, CartItem
from .serializers import (
    AddToCartSerializer,
    CartItemSerializer,
    CartSerializer,
    UpdateCartItemSerializer,
)


def get_user_cart(user):
    """Helper to get or create an optimized cart for the authenticated user"""
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


class CartView(APIView):
    """
    get:
    Retrieve the current authenticated user's shopping cart and summary.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart = get_user_cart(request.user)
        # Prefetch related products, categories and images
        cart = Cart.objects.prefetch_related(
            "items__product__category",
            "items__product__images"
        ).get(id=cart.id)
        serializer = CartSerializer(cart, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AddToCartView(APIView):
    """
    post:
    Add a product to the authenticated user's cart (or increment quantity if already present).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data["product_id"]
        quantity = serializer.validated_data.get("quantity", 1)

        product = get_object_or_404(Product, id=product_id)
        cart = get_user_cart(request.user)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={"quantity": quantity}
        )

        if not created:
            new_quantity = cart_item.quantity + quantity
            if new_quantity > product.stock:
                return Response(
                    {"quantity": f"Cannot add {quantity} more. Stock limit of {product.stock} reached."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            cart_item.quantity = new_quantity
            cart_item.save()

        # Return full updated cart
        cart = Cart.objects.prefetch_related(
            "items__product__category",
            "items__product__images"
        ).get(id=cart.id)
        response_serializer = CartSerializer(cart, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class UpdateCartItemView(APIView):
    """
    patch / put:
    Update the quantity of a specific cart item belonging to the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_cart_item(self, user, item_id):
        cart = get_user_cart(user)
        # Support lookup by item_id or product_id
        item = CartItem.objects.filter(cart=cart, id=item_id).first()
        if not item:
            item = CartItem.objects.filter(cart=cart, product_id=item_id).first()
        return item

    def patch(self, request, item_id):
        return self._update(request, item_id)

    def put(self, request, item_id):
        return self._update(request, item_id)

    def _update(self, request, item_id):
        cart_item = self._get_cart_item(request.user, item_id)
        if not cart_item:
            return Response(
                {"detail": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quantity = serializer.validated_data["quantity"]

        if quantity > cart_item.product.stock:
            return Response(
                {"quantity": f"Only {cart_item.product.stock} units available in stock."},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart_item.quantity = quantity
        cart_item.save()

        cart = Cart.objects.prefetch_related(
            "items__product__category",
            "items__product__images"
        ).get(id=cart_item.cart_id)
        response_serializer = CartSerializer(cart, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class RemoveCartItemView(APIView):
    """
    delete / post:
    Remove a specific cart item from the authenticated user's cart.
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, item_id):
        return self._remove(request, item_id)

    def post(self, request, item_id):
        return self._remove(request, item_id)

    def _remove(self, request, item_id):
        cart = get_user_cart(request.user)
        item = CartItem.objects.filter(cart=cart, id=item_id).first()
        if not item:
            item = CartItem.objects.filter(cart=cart, product_id=item_id).first()

        if not item:
            return Response(
                {"detail": "Cart item not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        item.delete()

        cart = Cart.objects.prefetch_related(
            "items__product__category",
            "items__product__images"
        ).get(id=cart.id)
        response_serializer = CartSerializer(cart, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class ClearCartView(APIView):
    """
    delete / post:
    Remove all items from the authenticated user's cart.
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        return self._clear(request)

    def post(self, request):
        return self._clear(request)

    def _clear(self, request):
        cart = get_user_cart(request.user)
        cart.items.all().delete()

        cart = Cart.objects.get(id=cart.id)
        response_serializer = CartSerializer(cart, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class SyncCartView(APIView):
    """
    post:
    Sync/migrate guest cart items to the authenticated user's cart upon login.
    Accepts: {"items": [{"product_id": 1, "quantity": 2}, ...]}
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        items_data = request.data.get("items", [])
        if not isinstance(items_data, list):
            return Response(
                {"detail": "items must be a list of objects containing product_id and quantity."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart = get_user_cart(request.user)

        with transaction.atomic():
            for entry in items_data:
                product_id = entry.get("product_id") or entry.get("id")
                qty = entry.get("quantity") or entry.get("qty") or 1
                try:
                    qty = int(qty)
                except (ValueError, TypeError):
                    continue

                if not product_id or qty < 1:
                    continue

                product = Product.objects.filter(id=product_id, is_active=True).first()
                if not product or product.stock <= 0:
                    continue

                actual_qty = min(qty, product.stock)

                cart_item, created = CartItem.objects.get_or_create(
                    cart=cart,
                    product=product,
                    defaults={"quantity": actual_qty},
                )
                if not created:
                    new_qty = min(cart_item.quantity + actual_qty, product.stock)
                    cart_item.quantity = new_qty
                    cart_item.save(update_fields=["quantity", "updated_at"])

        cart = Cart.objects.prefetch_related(
            "items__product__category",
            "items__product__images",
        ).get(id=cart.id)
        serializer = CartSerializer(cart, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
