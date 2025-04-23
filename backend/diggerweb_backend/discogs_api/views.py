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
from urllib.parse import urlencode

APPLICATION_AGENT_NAME = 'diggerweb/1.0'

DISCOGS_API_ERROR = 'Discogs API error'
ERROR_KEY = 'error'

# Executes module authorization once that the module is started or re-saved in development
DISCOGS_CONSUMER_KEY = os.getenv('DISCOGS_CONSUMER_KEY')
DISCOGS_CONSUMER_SECRET = os.getenv('DISCOGS_CONSUMER_SECRET')

DISCOGS_REQUEST_TOKEN_KEY = 'discogs_request_token'
DISCOGS_REQUEST_TOKEN_SECRET = 'discogs_request_secret'

DISCOGS_AUTHORIZE_KEY = 'discogs-authorize'

BASE_API_URL = 'https://api.discogs.com'
DISCOGS_MARKETPLACE_STATS_URL = "https://api.discogs.com/marketplace/stats/"

# Handles the authentication request from frontend to backend
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

# Handles authentication flow completion and return to application
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

            # Get access tokens and cleanup temporary ones
            access_token, access_secret = client.get_access_token(oauth_verifier)
            save_access_token(access_token, access_secret)
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

# Handles Discogs DB researches
class DiscogsSearchView(APIView):
        
    def searchUserInventory_API_Filtered(self, client, username, page_num, items_per_page):

        print(f"Looking for \"For Sale\" items at page {page_num} for user {username} ({items_per_page} items/pag)")

        # Default pagination info in case of early error
        pagination_info = {'page': page_num, 'pages': 0, 'per_page': items_per_page, 'items': 0, 'urls': {}}

        output_results = []

        try:
            # Build the complete research path
            endpoint = f'/users/{username}/inventory'

            params = {
                'status': 'For Sale',
                'page': page_num,
                'per_page': items_per_page,
            }

            query_string = urlencode(params)
            full_path_with_query = f"{BASE_API_URL}{endpoint}?{query_string}"

            # Execyte call and check results
            response_data = client._get(full_path_with_query)
            if not isinstance(response_data, dict) or 'pagination' not in response_data or 'listings' not in response_data:
                 print(f"Struttura risposta API inattesa: {response_data}")
                 raise ValueError("Struttura risposta invalida ricevuta dall'API Discogs")

            pagination_api = response_data.get('pagination', {})
            listings_data = response_data.get('listings', [])

            pagination_info = {
                'page': pagination_api.get('page', page_num),
                'pages': pagination_api.get('pages', 0),
                'per_page': pagination_api.get('per_page', items_per_page),
                'items': pagination_api.get('count', pagination_api.get('items', 0)),
                'urls': pagination_api.get('urls', {})
            }

            print(f"Received response. Paging: {pagination_info}. Listings ('For Sale') in page: {len(listings_data)}")

            for listing_dict in listings_data:
                try:

                    release_info = listing_dict.get('release', {})
                    release_id = release_info.get('id')
                    if not release_id:
                        continue

                    price_info = listing_dict.get('price', {})

                    stats_path = f"{DISCOGS_MARKETPLACE_STATS_URL}{release_id}"
                    stats_response = None
                    stats_error_msg = None

                    try:
                        stats_response = client._get(stats_path)
                        time.sleep(1)

                    except discogs_client.exceptions.HTTPError as stats_http_err:
                        print(f" HTTPError {stats_http_err.status_code} while retrieving stats for release {release_id}: {stats_http_err.msg}")
                        num_for_sale = None
                        stats_error_msg = f"Stats not available ({stats_http_err.status_code})"
                        time.sleep(1)

                    except Exception as stats_e:
                        print(f" Unexcpected error while retriveing stats for release {release_id}: {stats_e}")
                        num_for_sale = None
                        stats_error_msg = f"Error - Stats not availble"
                        time.sleep(1)

                    else:
                        num_for_sale = stats_response.get('num_for_sale') if stats_response else None

                    artists_list = release_info.get('artists', [])
                    artists_str = ", ".join(a.get('name', 'N/A') for a in artists_list) if artists_list else 'N/A'

                    item_data = {
                        'url': listing_dict.get('uri', listing_dict.get('resource_url')),
                        'release_id': release_id,
                        'title': release_info.get('description', 'N/A'), 
                        'artist': artists_str,
                        'num_for_sale': num_for_sale,
                        'price': price_info.get('value'),
                        'currency': price_info.get('currency'),
                        'condition': listing_dict.get('condition', 'N/A'),
                        'sleeve_condition': listing_dict.get('sleeve_condition', 'N/A'),
                        'id': listing_dict.get('id'),
                        'status': listing_dict.get('status')
                    }

                    if stats_error_msg:
                        item_data['stats_error'] = stats_error_msg

                    output_results.append(item_data)

                except Exception as item_e:
                    listing_id_str = listing_dict.get('id', 'Unknown')
                    print(f" Skipping item {listing_id_str} causes error during elaboration: {item_e}")
                    traceback.print_exc()
                    output_results.append({'id': listing_id_str,'error': f"Unexpected error while elaborating: {item_e}"})

            return output_results, pagination_info

        except discogs_client.exceptions.HTTPError as http_err:
             print(f"HTTPError during research for {username} (Page {page_num}): {http_err}")
             raise http_err
        
        except ValueError as val_err:
             print(f"ValueError during API elaboration: {val_err}")
             raise val_err
        
        except Exception as e:
            print(f"Unexpected error during research {username} (Pagie {page_num}): {e}")
            traceback.print_exc()
            return [], pagination_info

    def get(self, request, *args, **kwargs):

        access_token, access_secret = load_access_token()

        if not access_token or not access_secret:
            auth_url = request.build_absolute_uri(reverse(DISCOGS_AUTHORIZE_KEY))
            return Response({
                ERROR_KEY: "Discogs authorization required.",
                "authorize_url": auth_url
            }, status=status.HTTP_401_UNAUTHORIZED)

        client = discogs_client.Client(APPLICATION_AGENT_NAME)
        try:
            client.set_consumer_key(DISCOGS_CONSUMER_KEY, DISCOGS_CONSUMER_SECRET)
            client.set_token(access_token, access_secret)

            # Verify authentication by making a simple call
            identity = client.identity()
            print(f"Authenticated as Discogs user: {identity.username}")

        except (discogs_client.exceptions.HTTPError, discogs_client.exceptions.DiscogsAPIError) as auth_error:
            print(f"Discogs authentication failed: {auth_error}")
            auth_url = request.build_absolute_uri(reverse(DISCOGS_AUTHORIZE_KEY))
            return Response({
                ERROR_KEY: f"Invalid or expired Discogs credentials. Please re-authorize. ({auth_error})",
                "authorize_url": auth_url
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        except Exception as e:
             print(f"Error initializing Discogs client: {e}")
             traceback.print_exc()
             return Response({ERROR_KEY: f"Failed to initialize Discogs client: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        username = request.query_params.get('q')
        if not username:
             return Response({ERROR_KEY: "Missing 'q' parameter (username)."}, status=status.HTTP_400_BAD_REQUEST)

        # Get pagination parameters
        try:
            page_num = int(request.query_params.get('page', 1))
            items_per_page = int(request.query_params.get('per_page', 50))

            # Handle edge cases
            if items_per_page < 1:
                items_per_page = 1
            if items_per_page > 100:
                items_per_page = 100 # Respect Discogs limits (usually 100 max)
            if page_num < 1:
                page_num = 1

        except ValueError:
             return Response({ERROR_KEY: "'page' and 'per_page' parameters must be integers."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            output_results, pagination_info = self.searchUserInventory_API_Filtered(client, username, page_num, items_per_page)

            response_data = {
                'pagination': pagination_info,
                'results': output_results
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except discogs_client.exceptions.HTTPError as http_error:
            status_code = http_error.status_code if hasattr(http_error, 'status_code') else 500
            if status_code == 401: # Unauthorized during search - token might have been revoked
                 auth_url = request.build_absolute_uri(reverse(DISCOGS_AUTHORIZE_KEY))
                 return Response({
                      ERROR_KEY: f"Discogs API authentication error ({status_code}). Please re-authorize. ({http_error.msg})",
                      "authorize_url": auth_url
                 }, status=status_code)
            elif status_code == 404:
                 return Response({ERROR_KEY: f"Discogs user '{username}' not found or inventory is private/empty. ({http_error.msg})"}, status=status_code)
            else:
                 return Response({ERROR_KEY: f"{DISCOGS_API_ERROR} ({status_code}): {http_error.msg}"}, status=status_code)
        except discogs_client.exceptions.DiscogsAPIError as api_error:
            return Response({ERROR_KEY: f"{DISCOGS_API_ERROR}: {api_error}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            print(f"Unexpected server error during search for user {username}:")
            traceback.print_exc()
            return Response({ERROR_KEY: "Server internal error during research"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
