from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('cabinet/', views.cabinet, name='cabinet'),
    path('settings/', views.settings, name='settings'),
    path('login/', auth_views.LoginView.as_view(template_name='lab_queue_app/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_username_password, name='register'),
    path('register/captcha/', views.register_captcha, name='register_captcha'),
    path('register/email/', views.register_email, name='register_email'),
    path('register/verification-code/', views.register_verification_code, name='register_verification_code'),
    path('register/telegram-choice/', views.register_telegram_choice, name='register_telegram_choice'),
    path('register/telegram-link/', views.register_telegram_link, name='register_telegram_link'),
    path('register/study-group/', views.register_study_group, name='register_study_group'),
    path('check-telegram-bind/', views.check_telegram_bind, name='check_telegram_bind'),  # Новый маршрут
    path('join-queue/<int:work_id>/', views.join_queue, name='join_queue'),
    path('mark-served/<int:work_id>/', views.mark_served, name='mark_served'),
    path('cancel-served/<int:work_id>/', views.cancel_served, name='cancel_served'),
    path('leave-queue/<int:work_id>/', views.leave_queue, name='leave_queue'),
]