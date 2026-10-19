# E-Commerce REST API Backend

A scalable, modular RESTful API backend built with **Django 5** and **Django REST Framework (DRF)** for e-commerce platforms.

---

## Features

- **Authentication & User Management**:
  - Secure JWT authentication (`rest_framework_simplejwt`) with token rotation and blacklisting.
  - Multi-identifier login (supports username, email, or identifier).
  - User profiles and saved shipping/billing addresses.

- **Product Catalog & Categories**:
  - Full product listings with category filtering, price filtering, search, and pagination.
  - Product detail views with image galleries.
  - Stock tracking and active product guardrails.

- **Cart & Wishlist**:
  - Authenticated user cart with optimistic updates and stock validation.
  - Guest cart migration endpoint (`/api/cart/sync/`).
  - Wishlist management with quick toggle and one-click move-to-cart.

- **Orders & Checkout**:
  - Atomic checkout transaction with server-side pricing verification and stock decrement.
  - Customer order cancellation with automatic inventory restoration.
  - Order status history and admin fulfillment endpoints.

- **Payment Gateway Integration**:
  - Razorpay order creation and server-side HMAC-SHA256 signature verification.
  - Payment failure tracking and retry capabilities.

- **Reviews & Ratings**:
  - Verified buyer review submission.
  - Automatic calculation of product average ratings and review counts.

- **API Documentation & Security**:
  - Interactive Swagger UI (`/docs/`) and ReDoc (`/redoc/`) via `drf-yasg`.
  - Rate limiting / throttling on sensitive routes (`login`, `register`, `checkout`, `payment_verify`).
  - Production-ready security headers, CORS headers, and CSRF trusted origins.

---

## Tech Stack

- **Framework**: Django 5.x & Django REST Framework
- **Authentication**: `djangorestframework-simplejwt`
- **Database**: SQLite3
- **Payment Gateway**: Razorpay (`razorpay` Python SDK)
- **API Docs**: `drf-yasg` (OpenAPI 2.0 / Swagger)
- **Configuration**: `python-decouple`

---

## Project Structure

```text
e-c-backnd/
├── accounts/       # User auth, registration, profile & address book
├── cart/           # Shopping cart & guest-to-user sync
├── categories/     # Hierarchical product categories
├── config/         # Django project settings, URLs & security middleware
├── orders/         # Checkout, order creation & fulfillment
├── payment/        # Razorpay integration & webhook/signature verification
├── products/       # Product catalog, images, stock & filters
├── reviews/        # Verified reviews & rating recalculations
├── wishlist/       # User wishlist & move-to-cart operations
├── manage.py
└── requirements.txt
```

---

## Getting Started

### 1. Prerequisites

- Python 3.10 or higher
- Git

### 2. Clone & Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd e-c-backnd

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the project root (see `.env.example` for reference):

```ini
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# CORS & CSRF
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Razorpay Credentials (Optional for local development)
RAZORPAY_KEY_ID=rzp_test_eCommerceKey123
RAZORPAY_KEY_SECRET=rzp_test_secretKey456
```

### 4. Database Setup & Migrations

```bash
# Apply migrations
python manage.py migrate

# Create admin superuser
python manage.py createsuperuser
```

### 5. Run Development Server

```bash
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/`.

---

## API Endpoints

| Resource | Endpoint | Description |
|---|---|---|
| **Root** | `GET /` | Backend health & entry points |
| **Auth** | `POST /api/auth/register/` | Register a new user |
| **Auth** | `POST /api/auth/login/` | Obtain JWT tokens |
| **Auth** | `POST /api/auth/logout/` | Blacklist refresh token |
| **Auth** | `POST /api/auth/token/refresh/` | Refresh JWT access token |
| **Profile** | `GET, PUT, PATCH /api/auth/profile/` | Manage user profile |
| **Addresses** | `/api/accounts/addresses/` | Manage shipping addresses |
| **Categories**| `/api/categories/` | List product categories |
| **Products** | `/api/products/` | Catalog listing, filter & search |
| **Products** | `/api/products/<id_or_slug>/` | Product details |
| **Cart** | `GET /api/cart/` | View current user's cart |
| **Cart** | `POST /api/cart/add/` | Add item to cart |
| **Cart** | `POST /api/cart/sync/` | Sync guest items upon login |
| **Wishlist** | `GET /api/wishlist/` | View user's wishlist |
| **Wishlist** | `POST /api/wishlist/toggle/` | Toggle product in wishlist |
| **Orders** | `GET, POST /api/orders/` | List orders / Checkout |
| **Orders** | `POST /api/orders/<id>/cancel/`| Cancel pending order |
| **Payment** | `POST /api/payments/create-order/`| Create Razorpay order |
| **Payment** | `POST /api/payments/verify/` | Verify HMAC signature |
| **Payment** | `GET /api/payments/status/<order_id>/` | Check payment status |
| **Reviews** | `GET, POST /api/products/<id>/reviews/` | List / Submit reviews |

---

## API Documentation

Interactive API documentation is generated via Swagger and ReDoc:

- **Swagger UI**: [http://127.0.0.1:8000/docs/](http://127.0.0.1:8000/docs/)
- **ReDoc**: [http://127.0.0.1:8000/redoc/](http://127.0.0.1:8000/redoc/)
- **Django Admin**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## Running Tests

Run the full automated test suite with Django's test runner:

```bash
python manage.py test
```

To run tests for a specific application:

```bash
python manage.py test accounts
python manage.py test products
python manage.py test orders
python manage.py test payment
python manage.py test cart
python manage.py test wishlist
python manage.py test reviews
```
