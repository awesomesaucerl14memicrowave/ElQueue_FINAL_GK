from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from captcha.fields import ReCaptchaField
from captcha.widgets import ReCaptchaV2Checkbox
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re

class CustomUserCreationForm(UserCreationForm):
    username = forms.CharField(
        label=_('Имя пользователя'),
        min_length=4,
        max_length=30,
        help_text=_('Допустимые символы: буквы (кириллица/латиница), цифры и подчёркивание.'),
        error_messages={
            'unique': _('Это имя уже занято.'),
            'invalid': _('Недопустимые символы.')
        }
    )
    
    email = forms.EmailField(
        label=_('Электронная почта'),
        error_messages={
            'invalid': _('Некорректный формат email.'),
            'unique': _('Этот email уже зарегистрирован.')
        }
    )
    
    password1 = forms.CharField(
        label=_('Пароль'),
        widget=forms.PasswordInput,
        help_text=_('Минимум 8 символов, должны быть цифры и буквы.')
    )
    
    password2 = forms.CharField(
        label=_('Подтвердите пароль'),
        widget=forms.PasswordInput
    )
    
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'captcha')

    def clean_username(self):
        username = self.cleaned_data['username']
        if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9_]+$', username):
            raise ValidationError(_('Можно использовать только буквы, цифры и подчёркивание.'))
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
            raise ValidationError(_('Некорректный формат email.'))
        return email

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if len(password) < 8:
            raise ValidationError(_('Пароль должен быть не короче 8 символов.'))
        if not re.search(r'\d', password) or not re.search(r'[A-Za-z]', password):
            raise ValidationError(_('Пароль должен содержать буквы и цифры.'))
        return password

class ResendCaptchaForm(forms.Form):
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())