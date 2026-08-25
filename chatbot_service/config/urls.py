"""Root URL configuration for the chatbot API."""

from django.urls import include, path

urlpatterns = [
    path('api/', include('chatbot.urls')),
]
