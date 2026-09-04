from .settings import *

# Override throttling rates for standard test suite to prevent 429 Too Many Requests
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '10000/second',
    'user': '10000/second',
    'login': '10000/second',
    'register': '10000/second',
    'review': '10000/second',
    'checkout': '10000/second',
    'payment_verify': '10000/second',
}
