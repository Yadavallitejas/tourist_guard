# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

class CustomUser(AbstractUser):
    ROLE_CHOICES = (('tourist', 'Tourist'), ('police', 'Police'))
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def is_tourist(self):
        return self.role == 'tourist'
    def is_police(self):
        return self.role == 'police'


class TouristProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tourist_profile')
    full_name = models.CharField(max_length=200)
    age = models.PositiveIntegerField()
    phone_number = models.CharField(max_length=20)
    aadhaar_number = models.CharField(max_length=20)   # IMPORTANT: encrypt in production
    passport_id = models.CharField(max_length=50, blank=True, null=True)
    entry_date = models.DateField()
    leave_date = models.DateField()
    photo = models.ImageField(upload_to='tourists/photos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.user.username})"


class EmergencyContact(models.Model):
    tourist = models.ForeignKey(TouristProfile, on_delete=models.CASCADE, related_name='emergency_contacts')
    name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.name} - {self.phone}"


class PoliceProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='police_profile')
    station_name = models.CharField(max_length=200, blank=True, null=True)
    is_verified = models.BooleanField(default=False)   # can be used by admin to verify
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Police: {self.user.username} - {self.station_name or 'No station'}"

# accounts/models.py  (append)
from django.utils import timezone

class Location(models.Model):
    tourist = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='locations')
    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy = models.FloatField(null=True, blank=True)  # optional
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.tourist.username} @ {self.latitude},{self.longitude} at {self.timestamp}"


class SOSEvent(models.Model):
    tourist = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='sos_events')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)  # optional freeform
    # optionally store the summary lat/lon at creation
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"SOS: {self.tourist.username} at {self.created_at} (active={self.is_active})"
