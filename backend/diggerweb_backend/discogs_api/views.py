# Copyright 2025 Giorgio Gamba

from django.shortcuts import render

import os
import discogs_client
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status # Per usare codici di stato HTTP

# Inizializza il client Discogs una sola volta all'avvio del modulo
# Recuperando le credenziali dalle variabili d'ambiente (caricate in settings.py)
DISCOGS_USER_AGENT = os.getenv('DISCOGS_USER_AGENT')
DISCOGS_TOKEN = os.getenv('DISCOGS_API_TOKEN')

discogs_client_instance = None
initialization_error = None

if DISCOGS_USER_AGENT and DISCOGS_TOKEN:
    try:
        discogs_client_instance = discogs_client.Client('diggerweb/1.0', consumer_key=DISCOGS_USER_AGENT, consumer_secret=DISCOGS_TOKEN)
    except Exception as e:
        print(f"ERRORE CRITICO: Impossibile inizializzare Discogs Client: {e}")
        initialization_error = f"Errore interno del server: Discogs Client non configurato ({e})"
else:
    error_msg = "ERRORE CRITICO: DISCOGS_USER_AGENT o DISCOGS_API_TOKEN non trovati nelle variabili d'ambiente."
    print(error_msg)
    initialization_error = "Errore interno del server: Variabili Discogs mancanti."

class DiscogsSearchView(APIView):
    """
    Vista API per cercare su Discogs tramite la libreria discogs_client.
    Accetta parametri 'q' (query) e 'type' (opzionale).
    """
    def get(self, request, *args, **kwargs):

        # Controlla se il client è stato inizializzato correttamente
        if initialization_error:
            return Response({"error": initialization_error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if not discogs_client_instance:
             return Response({"error": "Errore interno del server: Discogs Client non disponibile."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        # Prendi i parametri dalla query string della richiesta GET
        query = request.query_params.get('q', None)
        search_type = request.query_params.get('type', 'release') # Default a 'release'

        if not query:
            return Response(
                {"error": "Il parametro 'q' (query) è obbligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Esegui la ricerca usando discogs_client
            results = discogs_client_instance.search(query, type=search_type)

            # Prepara i dati per la risposta JSON
            # Convertiamo gli oggetti Result in dizionari semplici
            output_results = []
            # Prendiamo solo la prima pagina (puoi aggiungere paginazione)
            page_num = int(request.query_params.get('page', 1)) # Supporta parametro 'page'
            items_per_page = 20 # Puoi renderlo un parametro

            if results and results.count > 0:
                # Itera sui risultati della pagina richiesta
                for result in results.page(page_num):
                     # Estrai i dati rilevanti. L'attributo '.data' è spesso utile.
                     item_data = {
                         'id': getattr(result, 'id', None),
                         'type': search_type, # Aggiungiamo il tipo cercato
                         'title': getattr(result, 'title', 'N/A'),
                         'thumb': getattr(result, 'thumb', ''), # URL miniatura
                         'cover_image': getattr(result, 'cover_image', ''), # URL copertina
                         'year': getattr(result, 'year', None),
                         # Aggiungi altri campi che ti interessano, es:
                         'country': getattr(result, 'country', None),
                         'formats': getattr(result, 'formats', None), # Questo potrebbe essere complesso
                         'uri': getattr(result, 'uri', None), # URI Discogs
                         # 'data': result.data # Opzione: includi tutti i dati grezzi
                     }
                     output_results.append(item_data)

            # Costruisci la risposta finale con risultati e paginazione
            response_data = {
                'pagination': {
                    'page': page_num,
                    'pages': results.pages if results else 0,
                    'per_page': items_per_page, # O la dimensione reale della pagina se diversa
                    'items': results.count if results else 0,
                    # 'urls': results.urls # URL per pagine successive/precedenti
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
