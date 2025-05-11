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


logger = logging.getLogger(__name__)

def index(request):
    return render(request, 'lab_queue_app/index.html')

@login_required
def cabinet(request):
    print("Cabinet - Request user:", request.user, type(request.user))  # Отладка
    # Проверяем, выбрана ли учебная группа
    user_study_groups = UserStudyGroup.objects.filter(user=request.user)  # Вернули user
    if not user_study_groups.exists():
        return render(request, 'lab_queue_app/cabinet.html', {
            'no_study_group': True,
            'profile': request.user.profile
        })

    # Получаем данные
    study_group = user_study_groups.first().study_group
    subjects = Subject.objects.filter(studygroupsubject__study_group=study_group)
    practical_works = PracticalWork.objects.filter(subject__in=subjects)
    
    # Активные очереди пользователя
    user_works = WaitingListParticipant.objects.filter(user=request.user, status='active')  # Вернули user
    user_work_subjects = set(work.practical_work.subject_id for work in user_works)
    
    # Карточки вставания в очередь (по предметам, где пользователь не в очереди)
    queue_cards = []
    for subject in subjects:
        if subject.id not in user_work_subjects:
            practical_works_for_subject = PracticalWork.objects.filter(subject=subject).order_by('sequence_number')
            served_works = WaitingListParticipant.objects.filter(
                user=request.user, practical_work__subject=subject, status='served'  # Вернули user
            ).values_list('practical_work_id', flat=True)
            available_works = practical_works_for_subject.exclude(id__in=served_works)
            if available_works.exists():
                first_work = available_works.first()
                queue_cards.append({
                    'subject': subject,
                    'available_works': ['{} | {} | {}'.format(work.id, work.sequence_number, work.name) for work in available_works],
                    'first_work_id': first_work.id,
                    'first_work_seq': first_work.sequence_number,
                    'first_work_name': first_work.name,
                })

    # Добавляем доступные лабы для "Мои предметы"
    practical_works_with_status = []
    for work in practical_works:
        participant = WaitingListParticipant.objects.filter(user=request.user, practical_work=work).first()  # Вернули user
        is_served = participant and participant.status == 'served'
        subject_works = PracticalWork.objects.filter(subject=work.subject).order_by('sequence_number')
        served_works = WaitingListParticipant.objects.filter(
            user=request.user, practical_work__subject=work.subject, status='served'  # Вернули user
        ).values_list('practical_work_id', flat=True)
        available_works = subject_works.exclude(id__in=served_works)
        practical_works_with_status.append({
            'work': work,
            'is_served': is_served,
            'participant': participant,
            'available_works': ['{} | {} | {}'.format(w.id, w.sequence_number, w.name) for w in available_works]
        })

    # Расписание
    slots = Schedule.objects.filter(subject__studygroupsubject__study_group=study_group)
    enriched_slots_dict = {}
    for slot in slots:
        start_time = datetime.combine(datetime.today(), slot.start_time)
        duration_minutes = slot.duration
        end_time = start_time + timedelta(minutes=duration_minutes)
        is_running = start_time <= datetime.now() <= end_time
        enriched_slots_dict[slot.subject.id] = {
            'subject': slot.subject,
            'weekday': slot.weekday,
            'week_type': slot.week_type,
            'start_time': slot.start_time,
            'end_time': end_time.strftime("%H:%M"),
            'duration': slot.duration,
            'is_running': is_running,
            'start_datetime': start_time
        }

    # Обогащаем user_works слотами
    enriched_user_works = []
    for work in user_works:
        slot_data = enriched_slots_dict.get(work.practical_work.subject_id, {})
        status_text = "Пара не идёт"
        if work.list_position == 1:
            status_text = "Первый в очереди"
        elif slot_data.get('is_running', False):
            status_text = "Пара идёт"
        enriched_user_works.append({
            'work': work,
            'slot': slot_data,
            'status_text': status_text
        })

    return render(request, 'lab_queue_app/cabinet.html', {
        'profile': request.user.profile,
        'study_group': study_group,
        'subjects': subjects,
        'practical_works_with_status': practical_works_with_status,
        'user_works': enriched_user_works,
        'slots': enriched_slots_dict.values(),
        'queue_cards': queue_cards,
    })

@login_required
def settings(request):
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
        username = request.POST.get('username')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if User.objects.filter(username=username).exists():
            return render(request, 'lab_queue_app/register_username_password.html',
                          {'error': 'Пользователь с таким именем уже существует.'})

        if password1 != password2:
            return render(request, 'lab_queue_app/register_username_password.html', {'error': 'Пароли не совпадают.'})

        if len(password1) < 8:
            return render(request, 'lab_queue_app/register_username_password.html',
                          {'error': 'Пароль должен содержать минимум 8 символов.'})

        request.session['register_data'] = {
            'username': username,
            'password': password1,
        }
        return redirect('register_captcha')

    return render(request, 'lab_queue_app/register_username_password.html')

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
    if request.method == 'POST':
        email = request.POST.get('email')
        code = request.POST.get('code')

        stored_code = request.session['register_data'].get('code')
        if not stored_code:
            return render(request, 'lab_queue_app/register_verification_code.html', {
                'email': email,
                'error': 'Код подтверждения не был сгенерирован. Пожалуйста, вернитесь на предыдущий шаг.'
            })

        if code != stored_code:
            return render(request, 'lab_queue_app/register_verification_code.html', {
                'email': email,
                'error': 'Неверный код.'
            })

        # Обновляем email в сессии
        register_data = request.session['register_data']
        register_data['email'] = email
        request.session['register_data'] = register_data
        request.session.modified = True  # Явно отмечаем, что сессия изменена
        print(f"Сессия перед логином: {request.session['register_data']}")  # Отладка

        # Создаём пользователя после успешного подтверждения почты
        user = User.objects.create_user(
            username=register_data['username'],
            password=register_data['password'],
            email=register_data['email']
        )
        # Создаём профиль
        UserProfile.objects.create(user=user)
        # Логиним пользователя
        login(request, user)

        # Сохраняем сессию после логина
        request.session['register_data'] = register_data
        request.session.modified = True
        print(f"Сессия после логина: {request.session['register_data']}")  # Отладка

        return redirect('register_telegram_choice')

    return render(request, 'lab_queue_app/register_verification_code.html', {'email': email})

def register_telegram_choice(request):
    print(f"Сессия на telegram_choice: {request.session.get('register_data', 'Отсутствует')}")
    # Временная отладка: уберём редирект, чтобы проверить шаблон
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
        bot_username = 'plaki_plaki_prod_bot'  # Замени на имя твоего бота (например, @YourBot)
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

        # Пользователь уже создан, профиль уже обновлён ботом, ничего не делаем с telegram_id
        user = request.user
        profile = user.profile
        # Удаляем эту строку, так как telegram_id уже установлен ботом
        # profile.telegram_id = register_data.get('telegram_id', '')
        profile.save()

        # Привязываем учебную группу
        study_group = StudyGroup.objects.get(id=study_group_id)
        UserStudyGroup.objects.create(user=user, study_group=study_group)

        # Очищаем сессию
        del request.session['register_data']

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
    if request.method == 'POST':
        work_id = request.POST.get('work_id')
        is_hurry = request.POST.get('is_hurry') == 'on'
        user = request.user
        if join_queue_util(user, work_id, is_hurry):
            return redirect('cabinet')
    return redirect('cabinet')

@login_required
def mark_served(request, work_id):
    if request.method == 'POST':
        practical_work = get_object_or_404(PracticalWork, id=work_id)
        participant = WaitingListParticipant.objects.filter(user=request.user, practical_work=practical_work).first()  # Вернули user
        if participant:
            participant.status = 'served'
            participant.save()
        else:
            WaitingListParticipant.objects.create(
                user=request.user,  # Вернули user
                practical_work=practical_work,
                status='served'
            )
        return redirect('cabinet')
    return redirect('cabinet')

@login_required
def cancel_served(request, work_id):
    if request.method == 'POST':
        practical_work = get_object_or_404(PracticalWork, id=work_id)
        participant = WaitingListParticipant.objects.filter(user=request.user, practical_work=practical_work).first()  # Вернули user
        if participant:
            if participant.status == 'served':
                participant.status = 'active'
                participant.save()
                WaitingListParticipant.recalculate_positions(practical_work.subject_id)
        return redirect('cabinet')
    return redirect('cabinet')

@login_required
def leave_queue(request, work_id):
    print("Request user:", request.user, 
          "Type:", type(request.user), 
          "Is authenticated:", request.user.is_authenticated, 
          "ID:", request.user.id)
    if request.method == 'POST':
        work_id = request.POST.get('work_id')
        has_passed = request.POST.get('has_passed') == 'on'
        user = request.user
        leave_queue_util(user, work_id, has_passed)
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