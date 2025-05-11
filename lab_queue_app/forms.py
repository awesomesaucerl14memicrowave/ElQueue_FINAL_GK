from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    captcha = forms.CharField(max_length=10, required=True, label="Введите 42 для проверки")

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'captcha')

    def clean_captcha(self):
        captcha = self.cleaned_data.get('captcha')
        if captcha != '42':
            raise forms.ValidationError('Неверный ответ на капчу.')
        return captcha
