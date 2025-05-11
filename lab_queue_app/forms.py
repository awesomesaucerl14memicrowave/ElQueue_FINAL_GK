from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from captcha.fields import ReCaptchaField
from captcha.widgets import ReCaptchaV2Checkbox

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    captcha = ReCaptchaField(
        widget=ReCaptchaV2Checkbox(),
        label=''
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'captcha')