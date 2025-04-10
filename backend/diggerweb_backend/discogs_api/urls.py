from django.urls import re_path, include
from .views import DiscogsSearchView

urlpatterns = [
	# Unique research endpoint
	re_path("search/", DiscogsSearchView.as_view(), name='discogs-search')
]
