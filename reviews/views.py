from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from products.models import Product
from .models import Review
from .permissions import IsReviewOwnerOrAdmin
from .serializers import (
    ReviewCreateSerializer,
    ReviewHistorySerializer,
    ReviewSerializer,
    ReviewUpdateSerializer,
)
from .utils import recalculate_product_ratings


class ProductReviewsView(APIView):
    """
    Endpoints for listing reviews of a product (Public) and submitting a new review (Authenticated & Verified).
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = 'review'
            return [ScopedRateThrottle()]
        return super().get_throttles()


    def get_product(self, pk_or_slug):
        if str(pk_or_slug).isdigit():
            return get_object_or_404(Product, pk=int(pk_or_slug))
        return get_object_or_404(Product, slug=pk_or_slug)

    @swagger_auto_schema(
        responses={
            200: openapi.Response(
                "Product Reviews List",
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "average_rating": openapi.Schema(type=openapi.TYPE_NUMBER),
                        "review_count": openapi.Schema(type=openapi.TYPE_INTEGER),
                        "results": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(type=openapi.TYPE_OBJECT),
                        ),
                    },
                ),
            ),
            404: "Product Not Found",
        }
    )
    def get(self, request, pk=None, pk_or_slug=None, *args, **kwargs):
        """
        Public endpoint to get reviews, average rating, and total count for a product.
        """
        identifier = pk or pk_or_slug
        product = self.get_product(identifier)
        reviews = (
            Review.objects.filter(product=product)
            .select_related("user", "product")
            .order_by("-created_at")
        )

        serializer = ReviewSerializer(reviews, many=True, context={"request": request})

        return Response(
            {
                "average_rating": float(product.average_rating),
                "review_count": product.review_count,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        request_body=ReviewCreateSerializer,
        responses={
            201: ReviewSerializer,
            400: "Validation error or not a verified buyer",
            401: "Unauthorized",
            404: "Product Not Found",
        },
    )
    def post(self, request, pk=None, pk_or_slug=None, *args, **kwargs):
        """
        Authenticated endpoint to create a review for a verified purchase.
        """
        identifier = pk or pk_or_slug
        product = self.get_product(identifier)

        serializer = ReviewCreateSerializer(
            data=request.data,
            context={"request": request, "product": product},
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            review = Review.objects.create(
                user=request.user,
                product=product,
                rating=serializer.validated_data["rating"],
                title=serializer.validated_data.get("title", ""),
                comment=serializer.validated_data["comment"],
                is_verified_purchase=True,
            )
            recalculate_product_ratings(product.id)

        response_serializer = ReviewSerializer(review, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ReviewDetailView(APIView):
    """
    Endpoints for editing (PATCH) and deleting (DELETE) a review by its author or an admin.
    """
    permission_classes = [permissions.IsAuthenticated, IsReviewOwnerOrAdmin]

    @swagger_auto_schema(
        request_body=ReviewUpdateSerializer,
        responses={
            200: ReviewSerializer,
            400: "Validation Error",
            403: "Permission Denied",
            404: "Review Not Found",
        },
    )
    def patch(self, request, pk=None, *args, **kwargs):
        review = get_object_or_404(Review.objects.select_related("product", "user"), pk=pk)
        self.check_object_permissions(request, review)

        serializer = ReviewUpdateSerializer(review, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            serializer.save()
            recalculate_product_ratings(review.product_id)

        response_serializer = ReviewSerializer(review, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        responses={
            200: openapi.Response("Review Deleted"),
            204: "No Content",
            403: "Permission Denied",
            404: "Review Not Found",
        }
    )
    def delete(self, request, pk=None, *args, **kwargs):
        review = get_object_or_404(Review.objects.select_related("product", "user"), pk=pk)
        self.check_object_permissions(request, review)

        product_id = review.product_id
        with transaction.atomic():
            review.delete()
            recalculate_product_ratings(product_id)

        return Response(
            {"detail": "Review deleted successfully."},
            status=status.HTTP_200_OK,
        )


class UserReviewHistoryView(generics.ListAPIView):
    """
    GET /api/my-reviews/
    Returns the authenticated user's submitted product reviews.
    """
    serializer_class = ReviewHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Review.objects.none()

        return (
            Review.objects.filter(user=self.request.user)
            .select_related("product", "user")
            .prefetch_related("product__images")
            .order_by("-created_at")
        )
