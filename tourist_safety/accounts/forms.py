# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser, TouristProfile, EmergencyContact
from django.conf import settings
from django.core.exceptions import ValidationError

class TouristRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    full_name = forms.CharField(max_length=200)
    age = forms.IntegerField(min_value=0)
    phone_number = forms.CharField(max_length=20)
    aadhaar_number = forms.CharField(max_length=20)
    passport_id = forms.CharField(max_length=50, required=False)
    entry_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    leave_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    photo = forms.ImageField(required=False)
    emergency_contacts = forms.CharField(
        required=False,
        help_text="Comma-separated contacts in the format: Name:Phone,Name2:Phone2"
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role = 'tourist'
        if commit:
            user.save()
            # create profile
            profile = TouristProfile.objects.create(
                user=user,
                full_name=self.cleaned_data['full_name'],
                age=self.cleaned_data['age'],
                phone_number=self.cleaned_data['phone_number'],
                aadhaar_number=self.cleaned_data['aadhaar_number'],
                passport_id=self.cleaned_data.get('passport_id'),
                entry_date=self.cleaned_data['entry_date'],
                leave_date=self.cleaned_data['leave_date'],
                photo=self.cleaned_data.get('photo'),
            )
            # parse emergency contacts
            raw = self.cleaned_data.get('emergency_contacts', '')
            for item in [i.strip() for i in raw.split(',') if i.strip()]:
                if ':' in item:
                    name, phone = item.split(':', 1)
                else:
                    name, phone = '', item
                EmergencyContact.objects.create(tourist=profile, name=name.strip(), phone=phone.strip())
        return user


class PoliceRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    registration_key = forms.CharField(widget=forms.PasswordInput, help_text="Secure key provided by admin")

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2')

    def clean_registration_key(self):
        key = self.cleaned_data.get('registration_key')
        allowed = [k.strip() for k in getattr(settings, 'POLICE_REGISTRATION_KEYS', []) if k.strip()]
        if key not in allowed:
            raise ValidationError("Invalid registration key. Contact admin.")
        return key

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role = 'police'
        if commit:
            user.save()
            # create police profile, mark verified (or leave admin to verify)
            from .models import PoliceProfile
            PoliceProfile.objects.create(user=user, is_verified=True)
        return user
