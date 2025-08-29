from django.urls import path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="suji V2 API",
        default_version='v1.0.0',
        description="""
        # suji V2 Game Platform API

        A comprehensive card game platform with social features, virtual economy, and competitive gameplay.

        ## Features
        - **Authentication**: JWT-based user authentication
        - **Match System**: Create and manage game matches
        - **Social Network**: Friend requests and player profiles
        - **Virtual Economy**: Shop, currencies, and rewards
        - **Leaderboards**: Competitive rankings and tournaments
        - **Statistics**: Player progression and analytics

        ## Authentication
        Most endpoints require authentication. Use the `Authorization: Bearer <token>` header.

        To get a token:
        1. Register/login via `/api/user/auth/player/login/` or `/api/user/auth/guest/login/`
        2. Use the returned access token in the Authorization header

        ## Rate Limiting
        Please be respectful with API calls. Excessive requests may be rate-limited.
        """,
        terms_of_service="https://github.com/sepehrNorouzi/suji-v2",
        contact=openapi.Contact(email="contact@yourdomain.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    authentication_classes=[],
)


swagger_urlpatterns = [
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
