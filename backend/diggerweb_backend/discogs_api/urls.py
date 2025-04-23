from django.urls import re_path, include
from .views import DiscogsSearchView, DiscogsAuthorizeView, DiscogsCallbackView

urlpatterns = [
	re_path("search/", DiscogsSearchView.as_view(), name='discogs-search'),
    re_path('authorize/', DiscogsAuthorizeView.as_view(), name='discogs-authorize'),
    re_path('callback/', DiscogsCallbackView.as_view(), name='discogs-callback')
]
