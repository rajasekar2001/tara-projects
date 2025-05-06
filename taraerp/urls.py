from django.http import HttpResponse
from django.contrib import admin
from django.urls import path, include

def home_view(request):
    return HttpResponse("Welcome to Tara ERP!")

urlpatterns = [
    path('', home_view),  # Root URL handler
    path('admin/', admin.site.urls),
    path('order/', include('order.urls')),
    path('user/', include('user.urls')),
    path('BusinessPartner/', include('BusinessPartner.urls')),
]
