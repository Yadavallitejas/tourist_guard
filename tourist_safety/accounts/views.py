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
from .models import Location, SOSEvent, SOSAudio
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
    events = SOSEvent.objects.filter(is_active=True).select_related('tourist').prefetch_related('audios').order_by('-created_at')[:200]
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
            'audio_files': [a.file.url for a in e.audios.all().order_by('uploaded_at')],
        })
    return JsonResponse({'events': out})

# accounts/views.py (append)
from io import BytesIO
from django.http import HttpResponse, Http404
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def generate_fir_pdf(request, sos_id):
    # Only police can generate FIR PDFs
    if not request.user.is_authenticated or not request.user.is_police():
        return HttpResponse(status=403, content="Forbidden: police access only.")

    try:
        sos = SOSEvent.objects.select_related('tourist').get(pk=sos_id)
    except SOSEvent.DoesNotExist:
        raise Http404("SOS event not found.")

    # Gather tourist information (sensitive data; police-only)
    tourist_user = sos.tourist
    tp = None
    try:
        tp = tourist_user.tourist_profile
    except Exception:
        tp = None

    # Gather recent locations for this SOS: last 10 minutes or related to the created_at
    # We'll take up to 50 most recent locations for context
    from django.utils import timezone
    ten_min_ago = sos.created_at - timezone.timedelta(minutes=10)
    locations = list(Location.objects.filter(tourist=tourist_user, timestamp__gte=ten_min_ago).order_by('timestamp')[:200])

    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    normal = styles['Normal']
    heading = styles['Heading1']
    small = ParagraphStyle('small', parent=normal, fontSize=9, leading=11)

    elements = []

    # Header
    elements.append(Paragraph("DIGITAL FIR - EMERGENCY SOS REPORT", heading))
    elements.append(Spacer(1, 12))

    # Meta
    elements.append(Paragraph(f"<b>FIR ID:</b> {sos.id}", normal))
    elements.append(Paragraph(f"<b>Generated by (police):</b> {request.user.get_full_name() or request.user.username}", normal))
    elements.append(Paragraph(f"<b>FIR Created At:</b> {sos.created_at.strftime('%Y-%m-%d %H:%M:%S %Z')}", normal))
    elements.append(Spacer(1, 12))

    # Tourist info block
    elements.append(Paragraph("<b>Tourist Information</b>", styles['Heading2']))
    t_rows = []
    t_rows.append(["Username", tourist_user.username])
    if tp:
        t_rows.append(["Full name", tp.full_name])
        t_rows.append(["Age", str(tp.age)])
        t_rows.append(["Phone", tp.phone_number])
        # Aadhaar/passport are sensitive; only included because police requested FIR
        t_rows.append(["Aadhaar / National ID", tp.aadhaar_number or ""])
        t_rows.append(["Passport ID", tp.passport_id or ""])
        t_rows.append(["Entry Date", tp.entry_date.isoformat()])
        t_rows.append(["Leave Date", tp.leave_date.isoformat()])
    else:
        t_rows.append(["Profile", "No tourist profile data available."])

    t_table = Table(t_rows, colWidths=[140, 340])
    t_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('BOX', (0,0), (-1,-1), 0.25, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_table)
    elements.append(Spacer(1, 12))

    # SOS summary
    elements.append(Paragraph("<b>SOS Event Summary</b>", styles['Heading2']))
    elements.append(Paragraph(f"<b>SOS Created at:</b> {sos.created_at.strftime('%Y-%m-%d %H:%M:%S %Z')}", normal))
    if sos.lat and sos.lon:
        elements.append(Paragraph(f"<b>Reported Location (summary):</b> {sos.lat}, {sos.lon}", normal))
    if sos.description:
        elements.append(Paragraph(f"<b>Description:</b> {sos.description}", normal))
    elements.append(Spacer(1, 12))

    # Locations table
    elements.append(Paragraph("<b>Recent Location Points (chronological)</b>", styles['Heading3']))
    if locations:
        loc_table_data = [["#", "Timestamp (ISO)", "Latitude", "Longitude", "Accuracy (m)"]]
        for i, loc in enumerate(locations, start=1):
            loc_table_data.append([
                str(i),
                loc.timestamp.astimezone().isoformat(),
                f"{loc.latitude:.6f}",
                f"{loc.longitude:.6f}",
                f"{loc.accuracy if loc.accuracy is not None else ''}"
            ])
        # Try to keep the table width reasonable
        loc_table = Table(loc_table_data, colWidths=[30, 160, 90, 90, 90])
        loc_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f0f0f0')),
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(loc_table)
    else:
        elements.append(Paragraph("No recent location points found for the 10 minutes before the SOS creation.", normal))

    elements.append(Spacer(1, 16))

    # Footer / signature placeholder
    elements.append(Paragraph("Statement:", styles['Heading3']))
    elements.append(Paragraph("This digital FIR was generated automatically from the SOS event record stored in the Tourist Safety System. For any further verification, please contact the station.", small))
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("Signature (Police Officer): ______________________", normal))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Station: {getattr(request.user, 'police_profile').station_name if hasattr(request.user, 'police_profile') else ''}", small))

    # Build the PDF
    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    filename = f"FIR_SOS_{sos.id}.pdf"
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write(pdf)
    return response

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import json

@csrf_exempt
@login_required
def upload_sos_audio(request, sos_id):
    if not request.user.is_tourist():
        return JsonResponse({"error": "Only tourists can upload audio."}, status=403)

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        sos = SOSEvent.objects.get(id=sos_id, tourist=request.user)
    except SOSEvent.DoesNotExist:
        return JsonResponse({"error": "SOS not found"}, status=404)

    if "audio" not in request.FILES:
        return JsonResponse({"error": "No audio file uploaded"}, status=400)

    audio_file = request.FILES["audio"]

    # Save file
    sos_audio = SOSAudio.objects.create(sos_event=sos, file=audio_file)

    return JsonResponse({
        "status": "ok",
        "audio_id": sos_audio.id,
        "file_url": sos_audio.file.url
    })
# accounts/views.py (inside get_sos_events)
def get_sos_events(request):
    if not request.user.is_police():
        return JsonResponse({"error": "Forbidden"}, status=403)

    events = SOSEvent.objects.select_related("tourist").prefetch_related("audios").order_by("-created_at")[:50]

    data = []
    for ev in events:
        # try full name, fallback to username
        try:
            name = ev.tourist.tourist_profile.full_name
        except:
            name = ev.tourist.username
        data.append({
            "sos_id": ev.id,
            "tourist": name,
            "lat": ev.lat,
            "lon": ev.lon,
            "created_at": ev.created_at.isoformat(),
            "audio_files": [a.file.url for a in ev.audios.order_by("uploaded_at")],
        })
    return JsonResponse({"events": data})

import math
from .models import DangerZone

def haversine(lat1, lon1, lat2, lon2):
    # returns distance in meters
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

def is_in_danger(lat, lon):
    for zone in DangerZone.objects.all():
        d = haversine(lat, lon, zone.center_lat, zone.center_lon)
        if d <= zone.radius_m:
            return zone
    return None

# accounts/views.py
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from django.http import JsonResponse

@csrf_exempt
def update_location(request):
    if not request.user.is_authenticated or not request.user.is_tourist():
        return JsonResponse({"error": "Forbidden"}, status=403)

    lat = float(request.POST.get("lat"))
    lon = float(request.POST.get("lon"))

    # Save location (optional: keep history)
    profile = request.user.tourist_profile
    profile.last_lat = lat
    profile.last_lon = lon
    profile.last_updated = now()
    profile.save()

    # Check geofence
    zone = is_in_danger(lat, lon)
    if zone:
        return JsonResponse({"status": "ok", "alert": f"You are entering danger zone: {zone.name}"})
    else:
        return JsonResponse({"status": "ok"})

def get_zones(request):
    zones = DangerZone.objects.all()
    return JsonResponse({"zones": [
        {"name": z.name, "lat": z.center_lat, "lon": z.center_lon, "radius_m": z.radius_m}
        for z in zones
    ]})

# accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import DangerZoneForm
from .models import DangerZone

@login_required
def dangerzone_list(request):
    if not request.user.is_police():
        return redirect("home")
    zones = DangerZone.objects.all()
    return render(request, "accounts/dangerzone_list.html", {"zones": zones})

@login_required
def dangerzone_create(request):
    if not request.user.is_police():
        return redirect("home")
    if request.method == "POST":
        form = DangerZoneForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("dangerzone_list")
    else:
        form = DangerZoneForm()
    return render(request, "accounts/dangerzone_form.html", {"form": form})

@login_required
def dangerzone_edit(request, pk):
    if not request.user.is_police():
        return redirect("home")
    zone = get_object_or_404(DangerZone, pk=pk)
    if request.method == "POST":
        form = DangerZoneForm(request.POST, instance=zone)
        if form.is_valid():
            form.save()
            return redirect("dangerzone_list")
    else:
        form = DangerZoneForm(instance=zone)
    return render(request, "accounts/dangerzone_form.html", {"form": form})

@login_required
def dangerzone_delete(request, pk):
    if not request.user.is_police():
        return redirect("home")
    zone = get_object_or_404(DangerZone, pk=pk)
    if request.method == "POST":
        zone.delete()
        return redirect("dangerzone_list")
    return render(request, "accounts/dangerzone_confirm_delete.html", {"zone": zone})
