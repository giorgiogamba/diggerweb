# Copyright 2025 Giorgio Gamba

from django.db import models

# Database model for authenticazione keys storage

class DiscogsCredentials(models.Model):
    # Assumes 8 byte unique tokens
    access_token = models.CharField(max_length=255, unique=True)
    access_secret = models.CharField(max_length=255)

    # When the class is instantied, then this is the time the keys are saved
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Discog Credentials (Updated: {self.last_updated})"
    
    class Meta:
        verbose_name_plural = "Discogs Credentials"
