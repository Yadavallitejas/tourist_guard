# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from .forms import TouristRegistrationForm, PoliceRegistrationForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponseForbidden
# accounts/views.py (append)
import json
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.utils import timezone
from .models import Location, SOSEvent
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt  # we prefer CSRF via token; keep login_required

@require_POST
@login_required
def api_location(request):
    # Only tourists should post locations
    if not request.user.is_tourist():
        return HttpResponseForbidden("Only tourists may post location.")
    try:
        data = json.loads(request.body)
        lat = float(data['latitude'])
        lon = float(data['longitude'])
        accuracy = float(data.get('accuracy')) if data.get('accuracy') is not None else None
        ts = data.get('timestamp')
        if ts:
            # expect ISO format
            timestamp = timezone.datetime.fromisoformat(ts)
            if timezone.is_naive(timestamp):
                timestamp = timezone.make_aware(timestamp, timezone.get_current_timezone())
        else:
            timestamp = timezone.now()
    except Exception as e:
        return HttpResponseBadRequest(f"Bad payload: {e}")
    Location.objects.create(tourist=request.user, latitude=lat, longitude=lon, accuracy=accuracy, timestamp=timestamp)
    return JsonResponse({'ok': True})


@require_POST
@login_required
def api_sos(request):
    if not request.user.is_tourist():
        return HttpResponseForbidden("Only tourists may send SOS.")
    try:
        data = json.loads(request.body)
        locations = data.get('locations', [])  # expected list of {latitude, longitude, timestamp}
        description = data.get('description', '')
    except Exception as e:
        return HttpResponseBadRequest(f"Bad JSON: {e}")

    # create SOSEvent using first/last loc summary
    if locations:
        # pick the latest location as summary
        latest = locations[-1]
        lat = float(latest['latitude'])
        lon = float(latest['longitude'])
    else:
        lat = lon = None

    sos = SOSEvent.objects.create(tourist=request.user, description=description, lat=lat, lon=lon)

    # store locations
    for loc in locations:
        try:
            ts = loc.get('timestamp')
            if ts:
                timestamp = timezone.datetime.fromisoformat(ts)
                if timezone.is_naive(timestamp):
                    timestamp = timezone.make_aware(timestamp, timezone.get_current_timezone())
            else:
                timestamp = timezone.now()
            Location.objects.create(
                tourist=request.user,
                latitude=float(loc['latitude']),
                longitude=float(loc['longitude']),
                accuracy=float(loc.get('accuracy')) if loc.get('accuracy') else None,
                timestamp=timestamp
            )
        except Exception:
            # skip malformed location entry
            continue

    # TODO: push realtime notification to police via channels / push service
    return JsonResponse({'ok': True, 'sos_id': sos.id, 'created_at': sos.created_at.isoformat()})

def register_tourist(request):
    if request.method == 'POST':
        form = TouristRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('tourist_home')
    else:
        form = TouristRegistrationForm()
    return render(request, 'accounts/register_tourist.html', {'form': form})


def register_police(request):
    if request.method == 'POST':
        form = PoliceRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('police_home')
    else:
        form = PoliceRegistrationForm()
    return render(request, 'accounts/register_police.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        user = request.user
        if user.is_tourist():
            return redirect('tourist_home')
        elif user.is_police():
            return redirect('police_home')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # redirect based on role
            if user.is_tourist():
                return redirect('tourist_home')
            elif user.is_police():
                return redirect('police_home')
            return redirect('login')
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def tourist_home(request):
    if not request.user.is_tourist():
        return HttpResponseForbidden("Not a tourist.")
    # Template will include SOS UI (JS will handle geo-permissions later)
    return render(request, 'accounts/tourist_home.html')


@login_required
def police_home(request):
    if not request.user.is_police():
        return HttpResponseForbidden("Not a police user.")
    # Later: show map & live data
    return render(request, 'accounts/police_home.html')


def logout_view(request):
    logout(request)
    return redirect('login')
# accounts/views.py (append)
from django.core.serializers import serialize
from django.views.decorators.http import require_GET
from django.utils.timezone import now

@require_GET
@login_required
def api_active_sos(request):
    # Only police can fetch this
    if not request.user.is_police():
        return HttpResponseForbidden("Only police can access SOS events.")
    # get active SOS events (optionally filter recent)
    events = SOSEvent.objects.filter(is_active=True).select_related('tourist').order_by('-created_at')[:200]
    out = []
    for e in events:
        # get last 1 location for this tourist (most recent)
        last_loc = Location.objects.filter(tourist=e.tourist).order_by('-timestamp').first()
        out.append({
            'sos_id': e.id,
            'tourist_username': e.tourist.username,
            'tourist_full_name': getattr(e.tourist, 'tourist_profile').full_name if hasattr(e.tourist, 'tourist_profile') else '',
            'created_at': e.created_at.isoformat(),
            'lat': e.lat or (last_loc.latitude if last_loc else None),
            'lon': e.lon or (last_loc.longitude if last_loc else None),
        })
    return JsonResponse({'events': out})
