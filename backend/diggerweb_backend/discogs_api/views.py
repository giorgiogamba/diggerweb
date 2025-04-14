# Copyright 2025 Giorgio Gamba

from django.shortcuts import render

import os
import traceback
import discogs_client
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import time

# Executes module authorization once that the module is started or re-saved in development
DISCOGS_USER_AGENT = os.getenv('DISCOGS_USER_AGENT')
DISCOGS_TOKEN = os.getenv('DISCOGS_API_TOKEN')

discogs_client_instance = None

# If populated, it means that the client was not properly initialized
initialization_error = None

if DISCOGS_USER_AGENT and DISCOGS_TOKEN:

    # #TODO refactor exeception handling
    try:
        discogs_client_instance = discogs_client.Client('diggerweb/1.0')

        discogs_client_instance.set_consumer_key(DISCOGS_USER_AGENT, DISCOGS_TOKEN)
        token, secret, url = discogs_client_instance.get_authorize_url()

        # Returns authorization URL and waiting for user to provide requested code
        print("authorize_url: ", url)
        oauth_verifier = input("Verification code : ")

        # Executes authorization
        access_token, access_secret = discogs_client_instance.get_access_token(oauth_verifier)

    except Exception as e:
        print(f"Critical error: impossible to authorize Discogs client {e}")
        initialization_error = f" ({e})"
else:
    print("Unable to find Discogs authorization values inside environment variables.")
    initialization_error = "Server side error: unable to find Discogs environment variables."

class DiscogsSearchView(APIView):
        
    def searchUserInventory(self, username):

        print("Searching releases for username " + str(username))

        user = discogs_client_instance.user(str(username))

        time.sleep(1) # In order to support discogs API restrictions

        releases = {}
        for listing in user.inventory:
            releaseId = listing.release.id

            stats_path = f"https://api.discogs.com/marketplace/stats/{releaseId}"
            stats_response = discogs_client_instance._get(stats_path)

            releases[listing.url] = stats_response.get('num_for_sale')

            time.sleep(1) # In order to support discogs API restrictions

        return releases

    def get(self, request, *args, **kwargs):
        
        # Client authorization check
        if initialization_error:
            return Response({"error": initialization_error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if not discogs_client_instance:
             return Response({"error": "Discogs client not available"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            results = self.searchUserInventory(request.query_params.get('q'))

            page_num = int(request.query_params.get('page', 1))
            items_per_page = 20 # #TODO refactor

            output_results = []

            for url, items in results.items():
                item_data = {
                    'url': url,
                    'items': items
                }

                output_results.append(item_data)

            # Build resulting page
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

        except discogs_client.exceptions.HTTPError as http_err:
            return Response({"error": f"Discogs API error ({http_err.status_code}): {http_err.msg}"}, status=http_err.status_code)
        except discogs_client.exceptions.DiscogsAPIError as api_err:
            return Response({"error": f"Discogs API error: {api_err}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            traceback.print_exc()
            return Response({"error": "Server internal error during research"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
