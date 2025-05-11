from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm
from .models import UserProfile, Subject, UserSubjectPreference, AvatarImage, PracticalWork, WaitingListParticipant, \
    Schedule, StudyGroup, UserStudyGroup, TelegramBindToken, StudyGroupSubject
from django.core.files.storage import FileSystemStorage
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.contrib import messages
import random
from django.http import JsonResponse, HttpResponse
import logging
from django.utils import timezone
from django.core.cache import cache
from .queue_utils import join_queue_util, leave_queue_util
from .schedule_utils import get_schedule_info
from django.conf import settings

logger = logging.getLogger(__name__)

@login_required
def index(request):
    """Главная страница: отображает секцию 'Встать в очередь'."""
    context = get_cabinet_data(request)
    return render(request, 'lab_queue_app/index.html', context)

@login_required
def cabinet(request):
    section = request.GET.get('section')
    work_id = request.GET.get('work_id')

    if section:
        if section == 'subjects' and work_id:
            user_study_groups = UserStudyGroup.objects.filter(user=request.user)
            if not user_study_groups.exists():
                return JsonResponse({'error': 'No study group selected'})
            study_group = user_study_groups.first().study_group
            subjects = Subject.objects.filter(studygroupsubject__study_group=study_group)
            for subject in subjects:
                for work in PracticalWork.objects.filter(subject=subject):
                    if str(work.id) == work_id:
                        participant = WaitingListParticipant.objects.filter(user=request.user, practical_work=work).first()
                        is_served = participant and participant.status == 'served' if participant else False
                        served_works = WaitingListParticipant.objects.filter(
                            user=request.user, practical_work__subject=subject, status='served'
                        ).values_list('practical_work_id', flat=True)
                        available_works = PracticalWork.objects.filter(subject=subject).exclude(id__in=served_works)
                        available_works_str = ', '.join(['{}|{}|{}'.format(w.id, w.sequence_number, w.name) for w in available_works])
                        return render(request, 'lab_queue_app/partials/work_item.html', {
                            'work': work,
                            'is_served': is_served,
                            'participant': participant,
                            'available_works_str': available_works_str
                        })
        elif section == 'subjects':
            context = get_cabinet_data(request)
            return render(request, 'lab_queue_app/partials/subjects_section.html', context)
        elif section == 'queues':
            context = get_cabinet_data(request)
            return render(request, 'lab_queue_app/partials/user_queues.html', context)
        elif section == 'queue-cards':
            context = get_cabinet_data(request)
            return render(request, 'lab_queue_app/partials/queue_cards.html', context)
        return JsonResponse({'error': 'Invalid section'})

    context = get_cabinet_data(request)
    return render(request, 'lab_queue_app/cabinet.html', context)

def get_cabinet_data(request):
    """Вспомогательная функция для подготовки данных кабинета."""
    user_study_groups = UserStudyGroup.objects.filter(user=request.user)
    if not user_study_groups.exists():
        return {'no_study_group': True, 'profile': request.user.profile}

    study_group = user_study_groups.first().study_group
    subjects = Subject.objects.filter(studygroupsubject__study_group=study_group)
    
    slots = Schedule.objects.filter(subject__studygroupsubject__study_group=study_group)
    schedule_info_dict = {slot.subject.id: get_schedule_info(slot) for slot in slots}

    subjects_with_works = []
    for subject in subjects:
        practical_works = PracticalWork.objects.filter(subject=subject).order_by('sequence_number')
        total_works = practical_works.count()
        works_with_status = []
        for work in practical_works:
            participant = WaitingListParticipant.objects.filter(user=request.user, practical_work=work).first()
            is_served = participant and participant.status == 'served' if participant else False
            served_works = WaitingListParticipant.objects.filter(
                user=request.user, practical_work__subject=subject, status='served'
            ).values_list('practical_work_id', flat=True)
            available_works = practical_works.exclude(id__in=served_works)
            available_works_str = ', '.join(['{}|{}|{}'.format(w.id, w.sequence_number, w.name) for w in available_works])
            works_with_status.append({
                'work': work,
                'is_served': is_served,
                'participant': participant,
                'available_works_str': available_works_str
            })
        served_count = WaitingListParticipant.objects.filter(
            user=request.user, practical_work__subject=subject, status='served'
        ).count()
        print(f"Subject: {subject.name}, Served: {served_count}, Total: {total_works}")  # Уже есть
        schedule_info = schedule_info_dict.get(subject.id, {
            'schedule_text': 'Нет расписания',
            'next_date': '',
            'is_running': False
        })
        # Отладка: убедимся, что данные передаются
        subject_data = {
            'subject': subject,
            'works': works_with_status,
            'schedule_text': schedule_info['schedule_text'],
            'next_date': schedule_info['next_date'],
            'is_running': schedule_info['is_running'],
            'served_count': served_count,
            'total_works': total_works,
        }
        print(f"Передаём в шаблон для {subject.name}: served_count={subject_data['served_count']}, total_works={subject_data['total_works']}")
        subjects_with_works.append(subject_data)

    # Формируем активные очереди
    user_works = WaitingListParticipant.objects.filter(user=request.user, status='active')
    user_work_subjects = set(work.practical_work.subject_id for work in user_works)
    
    # Формируем карточки для вставания в очередь
    queue_cards = []
    for subject in subjects:
        if subject.id not in user_work_subjects:
            practical_works_for_subject = PracticalWork.objects.filter(subject=subject).order_by('sequence_number')
            served_works = WaitingListParticipant.objects.filter(
                user=request.user, practical_work__subject=subject, status='served'
            ).values_list('practical_work_id', flat=True)
            available_works = practical_works_for_subject.exclude(id__in=served_works)
            if available_works.exists():
                first_work = available_works.first()
                queue_cards.append({
                    'subject': subject,
                    'available_works': ['{} | {} | {}'.format(work.id, work.sequence_number, w.name) for w in available_works],
                    'first_work_id': first_work.id,
                    'first_work_seq': first_work.sequence_number,
                    'first_work_name': first_work.name,
                })
            else:
                queue_cards.append({
                    'subject': subject,
                    'no_available_works': True
                })

    # Обогащаем user_works для отображения расписания
    enriched_user_works = []
    for work in user_works:
        subject_id = work.practical_work.subject_id
        schedule_info = schedule_info_dict.get(subject_id, {
            'schedule_text': 'Нет расписания',
            'next_date': '',
            'is_running': False
        })
        status_text = "Пара идёт" if schedule_info['is_running'] else schedule_info['next_date'] or "Пара не идёт"
        enriched_user_works.append({
            'work': work,
            'status_text': status_text,
            'is_running': schedule_info['is_running'],
            'next_date': schedule_info['next_date']
        })

    return {
        'profile': request.user.profile,
        'study_group': study_group,
        'subjects_with_works': subjects_with_works,
        'user_works': enriched_user_works,
        'queue_cards': queue_cards,
    }

def get_schedule_info(slot):
    """Получает информацию о расписании для предмета."""
    from datetime import datetime, timedelta
    current_datetime = datetime.now()
    current_time = current_datetime.time()
    current_weekday = current_datetime.weekday()  # 0 - Понедельник, 6 - Воскресенье

    # Определение целевого дня недели
    target_weekday = slot.weekday.order - 1  # Преобразуем 1-7 в 0-6
    if target_weekday < 0 or target_weekday > 6:
        target_weekday = 0

    start_time = slot.start_time
    end_time = (datetime.combine(current_datetime.date(), start_time) + timedelta(minutes=slot.duration)).time()

    # Проверка, идёт ли пара сейчас
    is_running = (
        target_weekday == current_weekday and
        start_time <= current_time <= end_time
    )

    # Формирование текста расписания
    schedule_text = f"{slot.weekday.name} {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} ({slot.week_type})"

    # Расчет следующей даты
    next_date = None
    if not is_running:
        days_ahead = (target_weekday - current_weekday) % 7
        if days_ahead == 0 and current_time > end_time:
            days_ahead = 7

        next_date_base = current_datetime.date() + timedelta(days=days_ahead)

        # Функция для определения начала учебного года
        def get_academic_year_start(date):
            return datetime(date.year - (1 if date.month < 9 else 0), 9, 1).date()

        september_first = get_academic_year_start(next_date_base)
        delta_days = (next_date_base - september_first).days
        academic_week_number = (delta_days // 7) + 1 if delta_days >= 0 else 0

        # Корректировка недели
        week_diff = 0
        if slot.week_type == 'even' and academic_week_number % 2 != 0:
            week_diff = 7
        elif slot.week_type == 'odd' and academic_week_number % 2 == 0:
            week_diff = 7

        next_date = next_date_base + timedelta(days=week_diff)
        next_date = datetime.combine(next_date, start_time)

        # Дополнительная проверка, если дата всё ещё в прошлом
        if next_date <= current_datetime:
            next_date += timedelta(days=7)

        next_date = next_date.strftime('%d.%m.%Y')

    return {
        'schedule_text': schedule_text,
        'next_date': next_date,
        'is_running': is_running
    }

@login_required
def user_settings(request):
    if not hasattr(request.user, 'profile'):
        UserProfile.objects.create(user=request.user)

    profile = request.user.profile
    subjects = Subject.objects.all()
    preferences = UserSubjectPreference.objects.filter(user=request.user)
    study_groups = StudyGroup.objects.all()

    if request.method == 'POST':
        theme = request.POST.get('theme')
        if theme in ['light', 'dark']:
            profile.theme = theme

        email_notifications = request.POST.get('email_notifications') == 'on'
        telegram_notifications = request.POST.get('telegram_notifications') == 'on'
        profile.email_notifications = email_notifications
        profile.telegram_notifications = telegram_notifications

        telegram_id = request.POST.get('telegram_id')
        profile.telegram_id = telegram_id

        email = request.POST.get('email')
        request.user.email = email
        request.user.save()

        if 'avatar' in request.FILES:
            avatar_file = request.FILES['avatar']
            avatar_image = AvatarImage.objects.create(image=avatar_file)
            profile.avatar = avatar_image

        profile.save()

        study_group_id = request.POST.get('study_group')
        if study_group_id and StudyGroup.objects.filter(id=study_group_id).exists():
            UserStudyGroup.objects.update_or_create(user=request.user, defaults={'study_group_id': study_group_id})

        for subject in subjects:
            is_visible = request.POST.get(f'subject_{subject.id}') == 'on'
            preference, created = UserSubjectPreference.objects.get_or_create(user=request.user, subject=subject)
            preference.is_visible = is_visible
            preference.save()

        return redirect('settings')

    return render(request, 'lab_queue_app/settings.html', {
        'profile': profile,
        'subjects': subjects,
        'preferences': {pref.subject.id: pref.is_visible for pref in preferences},
        'study_groups': study_groups,
        'user_study_group': UserStudyGroup.objects.filter(user=request.user).first()
    })

def register_username_password(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            code = str(random.randint(100000, 999999))
            print(f"Код подтверждения для {email}: {code}")
            request.session['register_data'] = {
                'username': username,
                'password': password,
                'email': email,
                'code': code
            }
            try:
                send_mail(
                    'Код подтверждения',
                    f'Ваш код подтверждения: {code}',
                    None,  # Используем DEFAULT_FROM_EMAIL из настроек
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                form.add_error('email', f'Не удалось отправить письмо: {e}')
                return render(request, 'lab_queue_app/register_username_password.html', {'form': form})
            return redirect('register_verification_code')
    else:
        form = CustomUserCreationForm()
    return render(request, 'lab_queue_app/register_username_password.html', {'form': form})

def register_captcha(request):
    if 'register_data' not in request.session:
        return redirect('register_username_password')

    if request.method == 'POST':
        captcha = request.POST.get('captcha')
        if captcha == '42':
            return redirect('register_email')
        return render(request, 'lab_queue_app/register_captcha.html', {'error': 'Неверный ответ на капчу.'})

    return render(request, 'lab_queue_app/register_captcha.html')

def register_email(request):
    if 'register_data' not in request.session:
        return redirect('register_username_password')

    if request.method == 'POST':
        email = request.POST.get('email')
        if User.objects.filter(email=email).exists():
            return render(request, 'lab_queue_app/register_email.html', {'error': 'Этот email уже используется.'})

        code = str(random.randint(100000, 999999))
        register_data = request.session['register_data']
        register_data['email'] = email
        register_data['code'] = code
        request.session['register_data'] = register_data

        print(f"Попытка отправки письма на {email} с кодом: {code}")
        try:
            send_mail(
                'Код подтверждения',
                f'Ваш код подтверждения: {code}',
                None,  # Используем DEFAULT_FROM_EMAIL из настроек
                [email],
                fail_silently=False,
            )
            print(f"Письмо успешно отправлено на {email}")
        except Exception as e:
            print(f"Ошибка при отправке письма: {e}")
            return render(request, 'lab_queue_app/register_email.html', {
                'error': f'Не удалось отправить письмо: {e}'
            })

        return redirect('register_verification_code')

    return render(request, 'lab_queue_app/register_email.html')

def register_verification_code(request):
    if 'register_data' not in request.session:
        return redirect('register')

    email = request.session['register_data'].get('email', '')
    resend_timeout = settings.VERIFICATION_CODE_RESEND_TIMEOUT
    now = int(timezone.now().timestamp())
    last_sent = request.session['register_data'].get('last_code_sent', 0)
    seconds_left = max(0, last_sent + resend_timeout - now)

    if request.method == 'POST':
        if 'resend' in request.POST:
            if seconds_left == 0:
                code = str(random.randint(100000, 999999))
                request.session['register_data']['code'] = code
                request.session['register_data']['last_code_sent'] = now
                request.session.modified = True
                print(f"Код подтверждения для {email}: {code}")
                try:
                    send_mail(
                        'Код подтверждения',
                        f'Ваш новый код подтверждения: {code}',
                        None,
                        [email],
                        fail_silently=False,
                    )
                except Exception as e:
                    return render(request, 'lab_queue_app/register_verification_code.html', {
                        'email': email,
                        'error': f'Не удалось отправить письмо: {e}',
                        'seconds_left': resend_timeout
                    })
                seconds_left = resend_timeout
            return render(request, 'lab_queue_app/register_verification_code.html', {
                'email': email,
                'message': 'Код отправлен повторно!',
                'seconds_left': seconds_left
            })
        # Обычная проверка кода
        code = request.POST.get('code')
        stored_code = request.session['register_data'].get('code')
        if not stored_code:
            return render(request, 'lab_queue_app/register_verification_code.html', {
                'email': email,
                'error': 'Код подтверждения не был сгенерирован. Пожалуйста, вернитесь на предыдущий шаг.',
                'seconds_left': seconds_left
            })
        if code != stored_code:
            return render(request, 'lab_queue_app/register_verification_code.html', {
                'email': email,
                'error': 'Неверный код.',
                'seconds_left': seconds_left
            })
        # Успешно: создаём пользователя
        register_data = request.session['register_data']
        user = User.objects.create_user(
            username=register_data['username'],
            password=register_data['password'],
            email=register_data['email']
        )
        UserProfile.objects.create(user=user)
        login(request, user)
        return redirect('register_telegram_choice')

    return render(request, 'lab_queue_app/register_verification_code.html', {
        'email': email,
        'seconds_left': seconds_left,
        'resend_timeout': resend_timeout
    })

def register_telegram_choice(request):
    if request.method == 'POST':
        if 'skip' in request.POST:
            return redirect('register_study_group')
        if 'link_telegram' in request.POST:
            token = TelegramBindToken.objects.create(user=request.user)
            bot_username = 'plaki_plaki_prod_bot'  # Замени на имя твоего бота
            deep_link = f"https://t.me/{bot_username}?start={token.token}"
            return redirect(deep_link)
    print(f"Сессия на telegram_choice: {request.session.get('register_data', 'Отсутствует')}")
    return render(request, 'lab_queue_app/register_telegram_choice.html')

def register_telegram_link(request):
    if 'register_data' not in request.session:
        return redirect('register')

    # Проверяем, привязан ли уже Telegram
    if request.user.profile.telegram_id:
        print(f"Telegram уже привязан: {request.user.profile.telegram_id}")
        return redirect('register_study_group')

    if request.method == 'POST':
        # Генерируем токен привязки
        token = TelegramBindToken.objects.create(user=request.user)
        # Формируем глубокую ссылку
        bot_username = 'plaki_plaki_prod_bot'  # Замени на имя твоего бота
        deep_link = f"https://t.me/{bot_username}?start={token.token}"
        return render(request, 'lab_queue_app/register_telegram_link.html', {
            'deep_link': deep_link,
            'message': 'Нажмите кнопку ниже, чтобы привязать Telegram.'
        })

    return render(request, 'lab_queue_app/register_telegram_link.html')

def register_study_group(request):
    if 'register_data' not in request.session:
        return redirect('register')

    study_groups = StudyGroup.objects.all()
    if request.method == 'POST':
        study_group_id = request.POST.get('study_group')
        if not study_group_id or not StudyGroup.objects.filter(id=study_group_id).exists():
            return render(request, 'lab_queue_app/register_study_group.html', {
                'study_groups': study_groups,
                'error': 'Выберите существующую учебную группу.'
            })

        # Пользователь уже создан, профиль уже обновлён ботом
        user = request.user
        profile = user.profile
        profile.save()

        # Привязываем учебную группу
        study_group = StudyGroup.objects.get(id=study_group_id)
        UserStudyGroup.objects.create(user=user, study_group=study_group)

        # Очищаем сессию
        request.session.pop('register_data', None)

        return redirect('cabinet')

    return render(request, 'lab_queue_app/register_study_group.html', {'study_groups': study_groups})

def logout_view(request):
    if request.method == 'POST':
        auth_logout(request)
        messages.success(request, "Вы успешно вышли из аккаунта.")
        return redirect('index')
    return redirect('index')

@login_required
def join_queue(request, work_id):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        is_hurry = request.POST.get('is_hurry') == 'on'
        participant, created = WaitingListParticipant.objects.get_or_create(
            user=request.user,
            practical_work_id=work_id,
            defaults={'status': 'active', 'is_hurry': is_hurry, 'list_position': 0}
        )
        if not created:
            participant.status = 'active'
            participant.save()
        return JsonResponse({'success': True})
    return redirect('cabinet')

@login_required
def mark_served(request, work_id):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            participant, created = WaitingListParticipant.objects.get_or_create(
                user=request.user,
                practical_work_id=work_id,
                defaults={'status': 'served', 'is_hurry': False, 'list_position': 0}
            )
            if not created:
                participant.status = 'served'
                participant.save()
            # Пересчитываем позиции
            work = PracticalWork.objects.get(id=work_id)
            WaitingListParticipant.recalculate_positions(work.subject_id)
            return JsonResponse({'success': True})
        except PracticalWork.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Work not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def cancel_served(request, work_id):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            participant = WaitingListParticipant.objects.filter(user=request.user, practical_work_id=work_id).first()
            if participant:
                participant.delete()
            # Пересчитываем позиции
            work = PracticalWork.objects.get(id=work_id)
            WaitingListParticipant.recalculate_positions(work.subject_id)
            return JsonResponse({'success': True})
        except PracticalWork.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Work not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def leave_queue(request, work_id):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        has_passed = request.POST.get('has_passed') == 'on'
        participant = WaitingListParticipant.objects.filter(user=request.user, practical_work_id=work_id).first()
        if participant:
            if has_passed:
                participant.status = 'served'
            else:
                participant.status = 'left'
            participant.save()
        return JsonResponse({'success': True})
    return redirect('cabinet')

def update_positions(work):
    participants = WaitingListParticipant.objects.filter(practical_work=work, status='active').order_by('is_hurry',
                                                                                                        'join_time')
    for i, participant in enumerate(participants, 1):
        participant.list_position = i
        participant.save()

def check_telegram_bind(request):
    if request.user.is_authenticated and request.user.profile.telegram_id:
        return JsonResponse({'is_bound': True})
    
@login_required
def check_work_status(request):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        work_id = request.POST.get('work_id')
        participant = WaitingListParticipant.objects.filter(user=request.user, practical_work_id=work_id).first()
        is_served = participant and participant.status == 'served' if participant else False
        return JsonResponse({'success': True, 'is_served': is_served})
    return JsonResponse({'success': False, 'error': 'Неверный запрос'})