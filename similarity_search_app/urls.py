from django.urls import path
from . import views

app_name = 'similarity_search_app'

urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('signin/', views.signin, name='signin'),
    path('signout/', views.signout, name='signout'),
    path('search/', views.search_ajax, name='search_ajax'),
    path('source-detail/', views.source_detail, name='source_detail'),
]