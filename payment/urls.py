from django.urls import path
from .views import (
    CreatePaymentOrderView,
    PaymentFailureView,
    PaymentStatusView,
    RetryPaymentView,
    VerifyPaymentView,
)

urlpatterns = [

    path("create-order/", CreatePaymentOrderView.as_view(), name="create_order"),
    path("verify/", VerifyPaymentView.as_view(), name="verify_payment"),
    path("status/<int:order_id>/", PaymentStatusView.as_view(), name="payment_status"),
    path("retry/", RetryPaymentView.as_view(), name="retry_payment"),
    path("failure/", PaymentFailureView.as_view(), name="payment_failure"),
]
