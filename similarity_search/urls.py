"""
URL configuration for similarity_search project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('similarity_search_app.urls')),
]