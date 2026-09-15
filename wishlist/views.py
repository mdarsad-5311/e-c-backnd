from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from cart.models import Cart, CartItem
from cart.serializers import CartSerializer
from products.models import Product
from .models import WishlistItem
from .serializers import AddWishlistSerializer, WishlistItemSerializer


class WishlistListView(APIView):
    """
    get:
    Retrieve the current authenticated user's wishlist.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = WishlistItem.objects.filter(user=request.user).select_related(
            "product__category"
        ).prefetch_related("product__images")

        serializer = WishlistItemSerializer(items, many=True, context={"request": request})
        return Response(
            {
                "count": items.count(),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK
        )


class AddWishlistView(APIView):
    """
    post:
    Add a product to the authenticated user's wishlist (duplicate safe).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AddWishlistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data["product_id"]
        product = get_object_or_404(Product, id=product_id)

        item, created = WishlistItem.objects.get_or_create(
            user=request.user,
            product=product
        )

        item_serializer = WishlistItemSerializer(item, context={"request": request})
        if not created:
            return Response(
                {
                    "detail": "Product is already in your wishlist.",
                    "is_already_wishlisted": True,
                    "item": item_serializer.data,
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                "detail": "Product added to wishlist.",
                "is_already_wishlisted": False,
                "item": item_serializer.data,
            },
            status=status.HTTP_201_CREATED
        )


class RemoveWishlistView(APIView):
    """
    delete / post:
    Remove a product from the authenticated user's wishlist.
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, product_id):
        return self._remove(request, product_id)

    def post(self, request, product_id):
        return self._remove(request, product_id)

    def _remove(self, request, product_id):
        # Support lookup by product_id or wishlist item id
        item = WishlistItem.objects.filter(user=request.user, product_id=product_id).first()
        if not item:
            item = WishlistItem.objects.filter(user=request.user, id=product_id).first()

        if not item:
            return Response(
                {"detail": "Product not found in your wishlist."},
                status=status.HTTP_404_NOT_FOUND
            )

        item.delete()
        return Response(
            {"detail": "Product removed from wishlist."},
            status=status.HTTP_200_OK
        )


class MoveToCartView(APIView):
    """
    post:
    Atomically move a wishlist item into the user's cart.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, product_id):
        # Lookup wishlist item
        item = WishlistItem.objects.filter(user=request.user, product_id=product_id).first()
        if not item:
            item = WishlistItem.objects.filter(user=request.user, id=product_id).first()

        if not item:
            return Response(
                {"detail": "Product not found in your wishlist."},
                status=status.HTTP_404_NOT_FOUND
            )

        product = item.product

        # Validate product active & stock
        if not product.is_active or (product.category and not product.category.is_active):
            return Response(
                {"detail": "This product is currently unavailable."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if product.stock <= 0:
            return Response(
                {"detail": "This product is currently out of stock."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Atomic transaction: Add to Cart & Remove from Wishlist
        with transaction.atomic():
            cart, _ = Cart.objects.get_or_create(user=request.user)
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                defaults={"quantity": 1}
            )

            if not created:
                if cart_item.quantity + 1 > product.stock:
                    return Response(
                        {"detail": f"Cannot add more. Stock limit of {product.stock} reached."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                cart_item.quantity += 1
                cart_item.save()

            # Remove from wishlist only after successful cart addition
            item.delete()

        # Return updated cart representation
        cart = Cart.objects.prefetch_related(
            "items__product__category",
            "items__product__images"
        ).get(id=cart.id)
        cart_serializer = CartSerializer(cart, context={"request": request})

        return Response(
            {
                "detail": "Product moved to cart successfully.",
                "cart": cart_serializer.data,
            },
            status=status.HTTP_200_OK
        )


class ToggleWishlistView(APIView):
    """
    post:
    Toggle product in authenticated user's wishlist (adds if absent, removes if present).
    Supports product_id via URL parameter or request body {"product_id": X}.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, product_id=None):
        if not product_id:
            product_id = request.data.get("product_id")
        
        if not product_id:
            return Response(
                {"detail": "product_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        product = get_object_or_404(Product, id=product_id)
        existing = WishlistItem.objects.filter(user=request.user, product=product).first()

        if existing:
            existing.delete()
            return Response(
                {
                    "detail": "Product removed from wishlist.",
                    "is_wishlisted": False,
                    "is_already_wishlisted": False,
                    "product_id": product.id,
                },
                status=status.HTTP_200_OK
            )
        else:
            item = WishlistItem.objects.create(user=request.user, product=product)
            item_serializer = WishlistItemSerializer(item, context={"request": request})
            return Response(
                {
                    "detail": "Product added to wishlist.",
                    "is_wishlisted": True,
                    "is_already_wishlisted": True,
                    "product_id": product.id,
                    "item": item_serializer.data,
                },
                status=status.HTTP_201_CREATED
            )
