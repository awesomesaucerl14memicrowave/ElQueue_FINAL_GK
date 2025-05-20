from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponseServerError, HttpResponseNotFound, HttpResponseForbidden

def handler403(request, exception=None):
    """
    Custom handler for 403 Forbidden errors (e.g., CSRF verification failed).
    """
    if not settings.CUSTOM_ERROR_PAGES:
        from django.views.defaults import permission_denied
        return permission_denied(request, exception)
    
    context = {
        'error_code': 403,
        'error_message': 'Ваша сессия истекла или действие недоступно. Пожалуйста, попробуйте снова.',
        'contact_link': 'https://t.me/yellow_cytrus',
    }
    return render(request, 'lab_queue_app/error.html', context, status=403)

def handler404(request, exception=None):
    """
    Custom handler for 404 Not Found errors.
    """
    if not settings.CUSTOM_ERROR_PAGES:
        from django.views.defaults import page_not_found
        return page_not_found(request, exception)
    
    context = {
        'error_code': 404,
        'error_message': 'Страница не найдена. Возможно, вы ввели неверный адрес.',
        'contact_link': 'https://t.me/yellow_cytrus',
    }
    return render(request, 'lab_queue_app/error.html', context, status=404)

def handler500(request, *args, **kwargs):
    """
    Custom handler for 500 Server Error.
    """
    if not settings.CUSTOM_ERROR_PAGES:
        from django.views.defaults import server_error
        return server_error(request)
    
    context = {
        'error_code': 500,
        'error_message': 'Произошла ошибка на сервере. Мы уже работаем над её исправлением.',
        'contact_link': 'https://t.me/yellow_cytrus',
    }
    return render(request, 'lab_queue_app/error.html', context, status=500)