# Copyright 2025 Giorgio Gamba

from django.shortcuts import render

import os
import traceback
import discogs_client
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import time
from django.urls import reverse
from .utils import save_access_token, load_access_token

APPLICATION_AGENT_NAME = 'diggerweb/1.0'

DISCOGS_API_ERROR = 'Discogs API error'
ERROR_KEY = 'error'

# Executes module authorization once that the module is started or re-saved in development
DISCOGS_CONSUMER_KEY = os.getenv('DISCOGS_CONSUMER_KEY')
DISCOGS_CONSUMER_SECRET = os.getenv('DISCOGS_CONSUMER_SECRET')

DISCOGS_REQUEST_TOKEN_KEY = 'discogs_request_token'
DISCOGS_REQUEST_TOKEN_SECRET = 'discogs_request_secret'

DISCOGS_AUTHORIZE_KEY = 'discogs-authorize'

class DiscogsAuthorizeView(APIView):
    def get(self, request, *args, **kwargs):
        client = discogs_client.Client(APPLICATION_AGENT_NAME)
        client.set_consumer_key(DISCOGS_CONSUMER_KEY, DISCOGS_CONSUMER_SECRET)

        try:
            callback_url = request.build_absolute_uri(reverse('discogs-callback'))

            request_token, request_secret, url = client.get_authorize_url(callback_url=callback_url)

            request.session[DISCOGS_REQUEST_TOKEN_KEY] = request_token
            request.session[DISCOGS_REQUEST_TOKEN_SECRET] = request_secret

            return Response({'authorization_url': url}, status=status.HTTP_200_OK)

        except discogs_client.exceptions.DiscogsAPIError as api_error:
            return Response({ERROR_KEY: f"{DISCOGS_API_ERROR}: {api_error}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            traceback.print_exc()
            return Response({ERROR_KEY: f"Server internal error during authorization initiation: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DiscogsCallbackView(APIView):

    def get(self, request, *args, **kwargs):

        oauth_verifier = request.query_params.get('oauth_verifier')
        oauth_token = request.query_params.get('oauth_token')

        if not oauth_verifier or not oauth_token:
            return Response({ERROR_KEY: "Missing oauth_verifier or oauth_token in callback"}, status=status.HTTP_400_BAD_REQUEST)

        client = discogs_client.Client(APPLICATION_AGENT_NAME)
        client.set_consumer_key(DISCOGS_CONSUMER_KEY, DISCOGS_CONSUMER_SECRET)

        if not client:
            return Response({ERROR_KEY: "Initialization error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            request_token = request.session.get(DISCOGS_REQUEST_TOKEN_KEY)
            request_secret = request.session.get(DISCOGS_REQUEST_TOKEN_SECRET)

            if not request_token or not request_secret:
                 return Response({ERROR_KEY: "Request token/secret not found (session expired or invalid?). Please restart authorization."}, status=status.HTTP_400_BAD_REQUEST)

            # Verify token correspondence
            if oauth_token != request_token:
                return Response({ERROR_KEY: "OAuth token mismatch."}, status=status.HTTP_400_BAD_REQUEST)

            client.set_token(request_token, request_secret)
            access_token, access_secret = client.get_access_token(oauth_verifier)

            # Saves inside application DB for further accesses
            save_access_token(access_token, access_secret)

            # Clean up temporary tokens because not needed anymore
            del request.session[DISCOGS_REQUEST_TOKEN_KEY]
            del request.session[DISCOGS_CONSUMER_SECRET]

            # TODO close popup via javascript
            return Response({"message": "Authorization successful! You can close this window."}, status=status.HTTP_200_OK)

        except discogs_client.exceptions.HTTPError as http_error:
            return Response({ERROR_KEY: f"{DISCOGS_API_ERROR} during token exchange ({http_error.status_code}): {http_error.msg}"}, status=http_error.status_code)
        except discogs_client.exceptions.DiscogsAPIError as api_error:
             return Response({ERROR_KEY: f"{DISCOGS_API_ERROR} during token exchange: {api_error}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            traceback.print_exc()
            return Response({ERROR_KEY: f"Server internal error during callback processing: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DiscogsSearchView(APIView):
        
    def searchUserInventory(self, client, username):
        print("Searching releases for username " + str(username))

        user = client.user(str(username))
        time.sleep(1) # In order to support discogs API restrictions

        releases = {}
        for listing in user.inventory:
            releaseId = listing.release.id

            stats_path = f"https://api.discogs.com/marketplace/stats/{releaseId}"
            stats_response = client._get(stats_path)

            releases[listing.url] = stats_response.get('num_for_sale')

            time.sleep(1) # In order to support discogs API restrictions

        return releases

    def get(self, request, *args, **kwargs):

        access_token, access_secret = load_access_token()

        if not access_token or not access_secret:
            authorize_url = reverse(DISCOGS_AUTHORIZE_KEY)

            return Response({
                ERROR_KEY: "Discogs authorization required.",
                "authorize_url": request.build_absolute_uri(authorize_url)
            }, status=status.HTTP_401_UNAUTHORIZED)

        client = discogs_client.Client(APPLICATION_AGENT_NAME)

        try:
            client.set_consumer_key(DISCOGS_CONSUMER_KEY, DISCOGS_CONSUMER_SECRET)
            client.set_token(access_token, access_secret)

        except Exception as e:
            # No credentials, reauthorize
            authorize_url = reverse(DISCOGS_AUTHORIZE_KEY)
            return Response({
                 ERROR_KEY: f"Invalid or expired Discogs credentials. Please re-authorize. ({e})",
                 "authorize_url": request.build_absolute_uri(authorize_url)
            }, status=status.HTTP_401_UNAUTHORIZED)

        username = request.query_params.get('q')
        if not username:
             return Response({ERROR_KEY: "Missing 'q' parameter (username)."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            results = self.searchUserInventory(client, username)
            page_num = int(request.query_params.get('page', 1))
            items_per_page = 20

            output_results = []

            for url, items in results.items():
                item_data = {'url': url, 'items': items}
                output_results.append(item_data)

            response_data = {
                'pagination': {
                    'page': page_num,
                    'pages': 0,
                    'per_page': items_per_page,
                    'items': 0
                },
                'results': output_results
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except discogs_client.exceptions.HTTPError as http_error:
            if http_error.status_code == 401:
                 authorize_url = reverse(DISCOGS_AUTHORIZE_KEY)
                 return Response({
                      "error": f"Discogs API authentication error ({http_error.status_code}). Please re-authorize. ({http_error.msg})",
                      "authorize_url": request.build_absolute_uri(authorize_url)
                 }, status=http_error.status_code)
            else:
                 return Response({"error": f"{DISCOGS_API_ERROR} ({http_error.status_code}): {http_error.msg}"}, status=http_error.status_code)
        except discogs_client.exceptions.DiscogsAPIError as api_error:
            return Response({"error": f"{DISCOGS_API_ERROR}: {api_error}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            traceback.print_exc()
            return Response({"error": "Server internal error during research"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        except discogs_client.exceptions.HTTPError as http_error:
            return Response({"error": f"{DISCOGS_API_ERROR} ({http_error.status_code}): {http_error.msg}"}, status=http_error.status_code)
        except discogs_client.exceptions.DiscogsAPIError as api_error:
            return Response({"error": f"{DISCOGS_API_ERROR}: {api_error}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            traceback.print_exc()
            return Response({"error": "Server internal error during research"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
