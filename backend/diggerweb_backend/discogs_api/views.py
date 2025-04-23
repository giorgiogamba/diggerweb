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
        
    def searchUserInventory(self, client, username, page_num, items_per_page):
        print("Searching releases for username " + str(username))

        user = client.user(str(username))
        time.sleep(1) # In order to support discogs API restrictions

        pagination_details = {
            'page': page_num,
            'pages': 0,
            'per_page': items_per_page,
            'items': 0,
            'urls': {}
        }

        output_results = []

        try:
            inventory = user.inventory
            inventory.per_page = items_per_page

            total_pages = inventory.pages
            total_items = inventory.count
            actual_per_page = inventory.per_page

            # Use getattr for safe access, returns None if attribute doesn't exist
            next_url = getattr(inventory, 'next', None)
            prev_url = getattr(inventory, 'prev', None)
            last_url = getattr(inventory, 'last', None)

            # Construct the urls dictionary manually based on found attributes
            page_urls = {}
            if next_url:
                page_urls['next'] = next_url
            if prev_url:
                page_urls['prev'] = prev_url
            if last_url:
                page_urls['last'] = last_url

            pagination_details = {
                'page': page_num, # The page we *intend* to fetch or are on
                'pages': total_pages,
                'per_page': actual_per_page,
                'items': total_items,
                'urls': page_urls
            }
            print(f"Pagination metadata: {pagination_details}")

            listings_on_page = inventory.page(page_num)
            print(f"Fetched page {page_num}. Items received: {len(listings_on_page)}")

            for listing in listings_on_page:

                try:
                    releaseId = listing.release.id
                    listing_url = listing.url

                    # TODO add caching if going back to prev page
                    stats_path = f"https://api.discogs.com/marketplace/stats/{releaseId}"
                    stats_response = client._get(stats_path)

                    num_for_sale = stats_response.get('num_for_sale') if stats_response else None

                    output_results.append({
                        'url': listing_url,
                        'release_id': releaseId,
                        'title': listing.release.title,
                        'artist': ", ".join(artist.name for artist in listing.release.artists),
                        'num_for_sale': num_for_sale,
                        'price': listing.price.value if listing.price else None,
                        'currency': listing.price.currency if listing.price else None,
                        'condition': listing.condition,
                        'sleeve_condition': listing.sleeve_condition,
                        'id': listing.id
                    })

                    time.sleep(1)

                except discogs_client.exceptions.DiscogsAPIError as item_api_error:
                    print(f" Skipping item {listing.id} due to Discogs API error: {item_api_error}")

                    output_results.append({
                        'url': listing.url if hasattr(listing, 'url') else 'N/A',
                        'release_id': 'N/A',
                        'error': f"Could not fetch stats: {item_api_error}"
                    })

                    time.sleep(1)

                except AttributeError as attr_error:
                     print(f" Skipping item due to missing attribute (data inconsistency?): {attr_error} on listing ID {listing.id if hasattr(listing, 'id') else 'Unknown'}")
                     output_results.append({
                        'url': listing.url if hasattr(listing, 'url') else 'N/A',
                        'release_id': 'N/A',
                        'error': f"Data inconsistency: {attr_error}"
                    })
                     
                except Exception as item_e:
                    print(f" Skipping item {listing.id if hasattr(listing, 'id') else 'Unknown'} due to unexpected error: {item_e}")
                    traceback.print_exc()
                    output_results.append({
                        'url': listing.url if hasattr(listing, 'url') else 'N/A',
                        'release_id': 'N/A',
                        'error': f"Unexpected error processing item: {item_e}"
                    })

                    time.sleep(1)

            return output_results, pagination_details

        except IndexError:
             # If requested page number is > total pages
             print(f"Requested page {page_num} is out of range.")

             try:
                 # Try to get pagination info even if the specific page failed
                 pagination_details['page'] = page_num

             except Exception as e:
                 print(f"Could not retrieve pagination details after page index error: {e}")

             return [], pagination_details

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
            output_results, pagination_info = self.searchUserInventory(client, username, page_num, items_per_page)

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
