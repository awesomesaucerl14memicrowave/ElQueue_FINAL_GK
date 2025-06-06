from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import CustomAuthenticationForm

urlpatterns = [
    path('', views.index, name='index'),
    path('cabinet/', views.cabinet, name='cabinet'),
    path('settings/', views.user_settings, name='user_settings'),
    path('settings/change-email/', views.change_email, name='change_email'),
    path('settings/password-reset/', views.password_reset_request, name='password_reset_request'),
    path('reset-password/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('login/', auth_views.LoginView.as_view(
        template_name='lab_queue_app/login.html',
        authentication_form=CustomAuthenticationForm
    ), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_username_password, name='register'),
    path('register/captcha/', views.register_captcha, name='register_captcha'),
    path('register/email/', views.register_email, name='register_email'),
    path('register/verification-code/', views.register_verification_code, name='register_verification_code'),
    path('register/telegram-choice/', views.register_telegram_choice, name='register_telegram_choice'),
    path('register/telegram-link/', views.register_telegram_link, name='register_telegram_link'),
    path('register/study-group/', views.register_study_group, name='register_study_group'),
    path('check-telegram-bind/', views.check_telegram_bind, name='check_telegram_bind'),
    path('join-queue/<int:work_id>/', views.join_queue, name='join_queue'),
    path('mark-served/<int:work_id>/', views.mark_served, name='mark_served'),
    path('cancel-served/<int:work_id>/', views.cancel_served, name='cancel_served'),
    path('leave-queue/<int:work_id>/', views.leave_queue, name='leave_queue'),
    path('check-work-status/', views.check_work_status, name='check_work_status'),
    path('queue/<int:work_id>/details/', views.queue_details, name='queue_details'),
    path('settings/telegram-link-request/', views.telegram_link_request, name='telegram_link_request'),
    path('settings/telegram-link-verify/', views.telegram_link_verify, name='telegram_link_verify'),
    path('settings/telegram-unlink-request/', views.telegram_unlink_request, name='telegram_unlink_request'),
    path('settings/telegram-unlink-verify/', views.telegram_unlink_verify, name='telegram_unlink_verify'),
    path('settings/register-telegram-link/', views.register_telegram_link, name='register_telegram_link'),
    path('check-username/', views.check_username, name='check_username'),
    path('check-email/', views.check_email, name='check_email'),
    path('queue-updates/', views.get_queue_updates, name='queue_updates'),
    path('check-telegram-status/', views.check_telegram_status, name='check_telegram_status'),
]