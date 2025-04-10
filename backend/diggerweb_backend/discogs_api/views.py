# Copyright 2025 Giorgio Gamba

from django.shortcuts import render

import os
import discogs_client
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status # Per usare codici di stato HTTP

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

        # Return authorization URL and waiting for user to provide requested code
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

    def get(self, request, *args, **kwargs):
        
        # Client authorization check
        if initialization_error:
            return Response({"error": initialization_error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if not discogs_client_instance:
             return Response({"error": "Discogs client not available"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        query = request.query_params.get('q', None)
        search_type = request.query_params.get('type', 'release')

        if not query:
            return Response(
                {"error": "Il parametro 'q' (query) è obbligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Executed research
            results = discogs_client_instance.search(query, type=search_type)

            # Convert results to JSON format
            output_results = []
            page_num = int(request.query_params.get('page', 1))
            items_per_page = 20 # #TODO refactor

            if results and results.count > 0:
                for result in results.page(page_num):
                     item_data = {
                         'id': getattr(result, 'id', None),
                         'type': search_type,
                         'title': getattr(result, 'title', 'N/A'),
                         'thumb': getattr(result, 'thumb', ''),
                         'cover_image': getattr(result, 'cover_image', ''),
                         'year': getattr(result, 'year', None),
                         'country': getattr(result, 'country', None),
                         'formats': getattr(result, 'formats', None),
                         'uri': getattr(result, 'uri', None),
                     }
                     output_results.append(item_data)

            # Build resulting page
            response_data = {
                'pagination': {
                    'page': page_num,
                    'pages': results.pages if results else 0,
                    'per_page': items_per_page,
                    'items': results.count if results else 0,
                },
                'results': output_results
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except discogs_client.exceptions.HTTPError as http_err:
            print(f"Discogs API HTTP Error: {http_err.status_code} - {http_err.msg}")
            return Response(
                {"error": f"Errore dall'API Discogs ({http_err.status_code}): {http_err.msg}"},
                status=http_err.status_code # Restituisci lo stesso codice di stato di Discogs
            )
        except discogs_client.exceptions.DiscogsAPIError as api_err:
            print(f"Discogs API Logic Error: {api_err}")
            return Response(
                {"error": f"Errore API Discogs: {api_err}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            print(f"Errore generico nella vista di ricerca Discogs: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {"error": "Errore interno del server durante la ricerca."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
