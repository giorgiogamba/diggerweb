# Copyright 2025 Giorgio Gamba

from .models import DiscogsCredentials

# Unique ID for just one line needed
CREDENTIALS_ID = 1

def save_access_token(token, secret):

    try:
        credentials, created = DiscogsCredentials.objects.update_or_create(
            pk=CREDENTIALS_ID,
            defaults={'access_token': token, 'access_secret': secret}
        )
        if created:
            print("Discogs credentials created in DB")
        else:
            print("Discogs credentials updated in DB")
        return True
    except Exception as e:
        print(f"Error while saving Discogs credentials: {e}")
        return False

def load_access_token():
    try:
        credentials = DiscogsCredentials.objects.filter(pk=CREDENTIALS_ID).first()
        if credentials:
            print("Loaded from DB Discogs Credentials")
            # TODO add cryptography
            return credentials.access_token, credentials.access_secret
        else:
            print("No Discogs Credentials found in the DB")
            return None, None
        
    except Exception as e:
        print(f"Error while loading Discogs credentials: {e}")
        return None, None