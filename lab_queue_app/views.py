import random
import time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.contrib import messages
from .forms import CustomUserCreationForm, ResendCaptchaForm, PasswordResetRequestForm, PasswordResetConfirmForm
from .models import EmailChangeAttempt, TelegramChangeAttempt, UserProfile, Subject, UserSubjectPreference, AvatarImage, PracticalWork, WaitingListParticipant, \
    Schedule, StudyGroup, UserStudyGroup, TelegramBindToken, StudyGroupSubject, PasswordResetAttempt
from django.core.files.storage import FileSystemStorage
from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponse
import logging
from django.utils import timezone
from django.core.cache import cache
from .queue_utils import join_queue_util, leave_queue_util
from .schedule_utils import get_schedule_info
from django.conf import settings
from captcha.fields import ReCaptchaField
from captcha.widgets import ReCaptchaV2Checkbox

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
        print(f"Subject: {subject.name}, Served: {served_count}, Total: {total_works}")
        schedule_info = schedule_info_dict.get(subject.id, {
            'schedule_text': 'Нет расписания',
            'next_date': '',
            'is_running': False
        })
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

    queue_cards = []
    for subject in subjects:
        practical_works_for_subject = PracticalWork.objects.filter(subject=subject).order_by('sequence_number')
        available_works = []
        for work in practical_works_for_subject:
            has_active = WaitingListParticipant.objects.filter(user=request.user, practical_work=work, status='active').exists()
            is_served = WaitingListParticipant.objects.filter(user=request.user, practical_work=work, status='served').exists()
            if not has_active and not is_served:
                available_works.append(work)
        if available_works:
            available_works_str = ', '.join(['{}|{}|{}'.format(w.id, w.sequence_number, w.name) for w in available_works])
            first_work = available_works[0]
            queue_cards.append({
                'subject': subject,
                'available_works': available_works,
                'available_works_str': available_works_str,
                'first_work_id': first_work.id,
                'first_work_seq': first_work.sequence_number,
                'first_work_name': first_work.name,
            })
    if not queue_cards:
        queue_cards.append({'no_available_works': True})

    user_works = WaitingListParticipant.objects.filter(user=request.user, status='active')
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
    current_weekday = current_datetime.weekday()

    target_weekday = slot.weekday.order - 1
    if target_weekday < 0 or target_weekday > 6:
        target_weekday = 0

    start_time = slot.start_time
    end_time = (datetime.combine(current_datetime.date(), start_time) + timedelta(minutes=slot.duration)).time()

    is_running = (
        target_weekday == current_weekday and
        start_time <= current_time <= end_time
    )

    schedule_text = f"{slot.weekday.name} {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} ({slot.week_type})"

    next_date = None
    if not is_running:
        days_ahead = (target_weekday - current_weekday) % 7
        if days_ahead == 0 and current_time > end_time:
            days_ahead = 7

        next_date_base = current_datetime.date() + timedelta(days=days_ahead)

        def get_academic_year_start(date):
            return datetime(date.year - (1 if date.month < 9 else 0), 9, 1).date()

        september_first = get_academic_year_start(next_date_base)
        delta_days = (next_date_base - september_first).days
        academic_week_number = (delta_days // 7) + 1 if delta_days >= 0 else 0

        week_diff = 0
        if slot.week_type == 'even' and academic_week_number % 2 != 0:
            week_diff = 7
        elif slot.week_type == 'odd' and academic_week_number % 2 == 0:
            week_diff = 7

        next_date = next_date_base + timedelta(days=week_diff)
        next_date = datetime.combine(next_date, start_time)

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
        if email:
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

        return redirect('user_settings')

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
                    None,
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
                None,
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

    register_data = request.session['register_data']
    email = register_data.get('email', '')
    now = int(timezone.now().timestamp())
    resend_timeout = settings.VERIFICATION_CODE_RESEND_TIMEOUT

    last_sent = register_data.get('last_code_sent', 0)
    seconds_left = max(0, last_sent + resend_timeout - now)

    attempts = request.session.get('verification_resend_attempts', [])
    attempts = [t for t in attempts if now - t < 600]
    request.session['verification_resend_attempts'] = attempts
    show_captcha = len(attempts) >= 3
    max_attempts = 5

    error = None
    captcha_form = None

    if request.method == 'POST':
        if 'resend' in request.POST:
            if len(attempts) >= max_attempts:
                return render(request, 'lab_queue_app/register_verification_code.html', {
                    'email': email,
                    'error': 'Слишком много попыток. Попробуйте позже.',
                    'seconds_left': seconds_left,
                    'resend_timeout': resend_timeout,
                    'show_captcha': show_captcha,
                    'captcha_form': None
                })

            if show_captcha:
                captcha_form = ResendCaptchaForm(request.POST)
                if not captcha_form.is_valid():
                    return render(request, 'lab_queue_app/register_verification_code.html', {
                        'email': email,
                        'error': 'Подтвердите, что вы не робот.',
                        'seconds_left': seconds_left,
                        'resend_timeout': resend_timeout,
                        'show_captcha': show_captcha,
                        'captcha_form': captcha_form
                    })

            code = str(random.randint(100000, 999999))
            register_data['code'] = code
            register_data['last_code_sent'] = now
            request.session['register_data'] = register_data
            request.session.modified = True

            attempts.append(now)
            request.session['verification_resend_attempts'] = attempts

            try:
                send_mail(
                    'Код подтверждения',
                    f'Ваш код подтверждения: {code}',
                    None,
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                return render(request, 'lab_queue_app/register_verification_code.html', {
                    'email': email,
                    'error': f'Не удалось отправить письмо: {e}',
                    'seconds_left': resend_timeout,
                    'resend_timeout': resend_timeout,
                    'show_captcha': show_captcha,
                    'captcha_form': captcha_form
                })

            seconds_left = resend_timeout
            return render(request, 'lab_queue_app/register_verification_code.html', {
                'email': email,
                'message': 'Код отправлен повторно!',
                'seconds_left': seconds_left,
                'resend_timeout': resend_timeout,
                'show_captcha': show_captcha,
                'captcha_form': captcha_form
            })

        code = request.POST.get('code')
        stored_code = register_data.get('code')

        if not stored_code:
            return render(request, 'lab_queue_app/register_verification_code.html', {
                'email': email,
                'error': 'Код не был сгенерирован. Вернитесь на шаг регистрации.',
                'seconds_left': seconds_left,
                'resend_timeout': resend_timeout,
                'show_captcha': show_captcha,
                'captcha_form': captcha_form
            })

        if code != stored_code:
            return render(request, 'lab_queue_app/register_verification_code.html', {
                'email': email,
                'error': 'Неверный код.',
                'seconds_left': seconds_left,
                'resend_timeout': resend_timeout,
                'show_captcha': show_captcha,
                'captcha_form': captcha_form
            })

        user = User.objects.create_user(
            username=register_data['username'],
            password=register_data['password'],
            email=email
        )
        UserProfile.objects.create(user=user)
        login(request, user)
        return redirect('register_telegram_choice')

    return render(request, 'lab_queue_app/register_verification_code.html', {
        'email': email,
        'seconds_left': seconds_left,
        'resend_timeout': resend_timeout,
        'show_captcha': show_captcha,
        'captcha_form': ResendCaptchaForm() if show_captcha else None
    })

def register_telegram_choice(request):
    if request.method == 'POST':
        if 'skip' in request.POST:
            return redirect('register_study_group')
        if 'link_telegram' in request.POST:
            token = TelegramBindToken.objects.create(user=request.user)
            bot_username = 'plaki_plaki_prod_bot'
            deep_link = f"https://t.me/{bot_username}?start={token.token}"
            return redirect(deep_link)
    print(f"Сессия на telegram_choice: {request.session.get('register_data', 'Отсутствует')}")
    return render(request, 'lab_queue_app/register_telegram_choice.html')

def register_telegram_link(request):
    if 'register_data' not in request.session:
        return redirect('register')

    if request.user.profile.telegram_id:
        print(f"Telegram уже привязан: {request.user.profile.telegram_id}")
        return redirect('register_study_group')

    if request.method == 'POST':
        token = TelegramBindToken.objects.create(user=request.user)
        bot_username = 'plaki_plaki_prod_bot'
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

        user = request.user
        profile = user.profile
        profile.save()

        study_group = StudyGroup.objects.get(id=study_group_id)
        UserStudyGroup.objects.create(user=user, study_group=study_group)

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
    if request.method == 'POST':
        try:
            print(f"Join queue request - User: {request.user}, Work ID: {work_id}")
            print(f"POST data: {request.POST}")
            print(f"Headers: {request.headers}")
            
            is_hurry = request.POST.get('is_hurry') == 'on'
            print(f"Is hurry: {is_hurry}")
            
            existing_participant = WaitingListParticipant.objects.filter(
                user=request.user,
                practical_work_id=work_id,
                status='active'
            ).first()
            
            if existing_participant:
                return JsonResponse({
                    'success': False,
                    'error': 'Вы уже стоите в этой очереди'
                })
            
            participant = WaitingListParticipant.objects.create(
                user=request.user,
                practical_work_id=work_id,
                status='active',
                is_hurry=is_hurry,
                list_position=0
            )
            
            work = PracticalWork.objects.get(id=work_id)
            WaitingListParticipant.recalculate_positions(work.subject_id)
            
            return JsonResponse({
                'success': True,
                'message': 'Вы успешно встали в очередь'
            })
        except Exception as e:
            print(f"Error in join_queue: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    return JsonResponse({
        'success': False,
        'error': 'Неверный метод запроса'
    }, status=400)

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
            work = PracticalWork.objects.get(id=work_id)
            WaitingListParticipant.recalculate_positions(work.subject_id)
            return JsonResponse({'success': True})
        except PracticalWork.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Work not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def leave_queue(request, work_id):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            has_passed = request.POST.get('has_passed') == 'on'
            participant = WaitingListParticipant.objects.filter(
                user=request.user, 
                practical_work_id=work_id,
                status='active'
            ).first()
            
            if participant:
                if has_passed:
                    participant.status = 'served'
                else:
                    participant.status = 'left'
                participant.save()
                
                WaitingListParticipant.recalculate_positions(participant.practical_work.subject_id)
                
                return JsonResponse({
                    'success': True,
                    'message': 'Вы успешно вышли из очереди'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Вы не состоите в этой очереди'
                })
        except Exception as e:
            print(f"Error in leave_queue: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    return JsonResponse({
        'success': False,
        'error': 'Неверный метод запроса'
    }, status=400)

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

@login_required
def queue_details(request, work_id):
    work = get_object_or_404(PracticalWork, id=work_id)
    active_participants = WaitingListParticipant.objects.filter(
        practical_work=work,
        status__in=['active', 'hurry']
    ).select_related('user').order_by('-is_hurry', 'list_position')
    
    is_in_queue = False
    user_position = None
    if request.user.is_authenticated:
        user_participant = WaitingListParticipant.objects.filter(
            user=request.user,
            practical_work=work,
            status__in=['active', 'hurry']
        ).first()
        is_in_queue = user_participant is not None
        if is_in_queue:
            user_position = user_participant.list_position
    
    context = {
        'work': work,
        'active_participants': active_participants,
        'active_participants_count': active_participants.count(),
        'is_in_queue': is_in_queue,
        'user_position': user_position,
    }
    return render(request, 'lab_queue_app/queue_details.html', context)

@login_required
def change_email(request):
    now = int(time.time())
    session_key = 'email_change_data'
    data = request.session.get(session_key, {})

    if 'email' not in data:
        data['email'] = ''
        data['code'] = ''
        data['last_code_sent'] = 0
        data['attempts'] = []

    request.session[session_key] = data
    request.session.modified = True

    email = data.get('email', '')
    seconds_left = max(0, data['last_code_sent'] + settings.VERIFICATION_CODE_RESEND_TIMEOUT - now)
    show_captcha = len(data['attempts']) >= 3
    captcha_form = ResendCaptchaForm(request.POST or None) if show_captcha else None
    code = request.POST.get('code')
    resend_requested = 'resend' in request.POST
    new_email = request.POST.get('new_email', email)
    error, message = None, None

    if request.method == 'POST' and not resend_requested and code:
        if code != data.get('code'):
            error = 'Неверный код.'
        else:
            if User.objects.filter(email=data['email']).exclude(id=request.user.id).exists():
                error = 'Пользователь с такой почтой уже существует.'
            else:
                request.user.email = data['email']
                request.user.save()
                request.session.pop(session_key, None)
                messages.success(request, 'Почта успешно изменена.')
                return redirect('user_settings')

    if resend_requested or ('send_code' in request.POST):
        if new_email == request.user.email:
            error = 'Новый email совпадает с текущим.'
        elif User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
            error = 'Пользователь с такой почтой уже зарегистрирован.'
        elif len(data['attempts']) >= 5:
            error = 'Слишком много попыток. Попробуйте позже.'
        elif show_captcha and captcha_form and not captcha_form.is_valid():
            error = 'Подтвердите, что вы не робот.'
        elif seconds_left > 0:
            error = f'Повторная отправка будет доступна через {seconds_left} секунд.'
        else:
            new_code = str(random.randint(100000, 999999))
            data.update({
                'email': new_email,
                'code': new_code,
                'last_code_sent': now,
            })
            data['attempts'].append(now)
            request.session[session_key] = data
            request.session.modified = True

            print(f'Код для {new_email}: {new_code}')

            try:
                send_mail(
                    'Код подтверждения смены почты',
                    f'Ваш код подтверждения: {new_code}',
                    None,
                    [new_email],
                    fail_silently=False
                )
                message = 'Код отправлен.'
            except Exception as e:
                error = f'Ошибка при отправке: {e}'

            seconds_left = settings.VERIFICATION_CODE_RESEND_TIMEOUT + 10 * (len(data["attempts"]) - 1)

    return render(request, 'lab_queue_app/change_email.html', {
        'email': data['email'],
        'new_email': new_email,
        'seconds_left': seconds_left,
        'show_captcha': show_captcha,
        'captcha_form': captcha_form,
        'error': error,
        'message': message
    })

def password_reset_request(request):
    now = int(time.time())
    session_key = 'password_reset_data'
    data = request.session.get(session_key, {})
    
    if 'email' not in data:
        data['email'] = ''
        data['last_sent'] = 0
        data['attempts'] = []

    request.session[session_key] = data
    request.session.modified = True

    email = data.get('email', '')
    seconds_left = max(0, data['last_sent'] + settings.VERIFICATION_CODE_RESEND_TIMEOUT - now)
    show_captcha = len(data['attempts']) >= 3
    captcha_form = ResendCaptchaForm(request.POST or None) if show_captcha else None
    error, message = None, None

    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            data['email'] = email
            request.session[session_key] = data
            request.session.modified = True

            if seconds_left > 0:
                error = f'Повторная отправка будет доступна через {seconds_left} секунд.'
            elif show_captcha and captcha_form and not captcha_form.is_valid():
                error = 'Подтвердите, что вы не робот.'
            elif len(data['attempts']) >= 5:
                error = 'Слишком много попыток. Попробуйте позже.'
            else:
                user = User.objects.filter(email=email).first()
                if user:
                    token_generator = PasswordResetTokenGenerator()
                    token = token_generator.make_token(user)
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    reset_link = request.build_absolute_uri(f'/reset-password/{uid}/{token}/')
                    
                    try:
                        send_mail(
                            'Сброс пароля',
                            f'Для сброса пароля перейдите по ссылке: {reset_link}\n\n'
                            f'Ссылка действительна в течение 2 часов.\n'
                            f'Если вы не запрашивали сброс пароля, проигнорируйте это письмо.',
                            None,
                            [email],
                            fail_silently=False,
                        )
                        reset_attempt, _ = PasswordResetAttempt.objects.get_or_create(user=user)
                        reset_attempt.increment()
                        data['last_sent'] = now
                        data['attempts'].append(now)
                        request.session[session_key] = data
                        request.session.modified = True
                        message = 'Если этот email зарегистрирован, мы отправили вам письмо с инструкциями.'
                    except Exception as e:
                        error = f'Ошибка при отправке письма: {e}'
                else:
                    message = 'Если этот email зарегистрирован, мы отправили вам письмо с инструкциями.'

                seconds_left = settings.VERIFICATION_CODE_RESEND_TIMEOUT + 10 * (len(data['attempts']) - 1)
        else:
            error = 'Пожалуйста, введите корректный email.'
    else:
        form = PasswordResetRequestForm()

    return render(request, 'lab_queue_app/password_reset_request.html', {
        'form': form,
        'email': email,
        'seconds_left': seconds_left,
        'show_captcha': show_captcha,
        'captcha_form': captcha_form,
        'error': error,
        'message': message,
        'resend_timeout': settings.VERIFICATION_CODE_RESEND_TIMEOUT,
    })

def password_reset_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    token_generator = PasswordResetTokenGenerator()
    if user and token_generator.check_token(user, token):
        if request.method == 'POST':
            form = PasswordResetConfirmForm(request.POST)
            if form.is_valid():
                user.set_password(form.cleaned_data['password1'])
                user.save()
                
                try:
                    send_mail(
                        'Пароль успешно изменён',
                        'Ваш пароль был успешно изменён. Если это были не вы, срочно свяжитесь с поддержкой.',
                        None,
                        [user.email],
                        fail_silently=False,
                    )
                except Exception as e:
                    messages.warning(request, f'Пароль изменён, но не удалось отправить уведомление: {e}')

                login(request, user)
                messages.success(request, 'Пароль успешно изменён.')
                return redirect('user_settings')
        else:
            form = PasswordResetConfirmForm()
        return render(request, 'lab_queue_app/password_reset_confirm.html', {
            'form': form,
            'validlink': True,
        })
    else:
        return render(request, 'lab_queue_app/password_reset_confirm.html', {
            'validlink': False,
            'error': 'Ссылка недействительна или истек срок её действия.'
        })
    

@login_required
def telegram_link_request(request):
    """Запрос кода для привязки Telegram."""
    now = int(timezone.now().timestamp())
    session_key = 'telegram_link_data'
    data = request.session.get(session_key, {
        'code': '',
        'last_code_sent': 0,
        'attempts': [],
    })

    seconds_left = max(0, data['last_code_sent'] + settings.VERIFICATION_CODE_RESEND_TIMEOUT - now)
    attempts = [t for t in data.get('attempts', []) if now - t < 600]
    show_captcha = len(attempts) >= 3
    max_attempts = 5
    error, message = None, None
    captcha_form = ResendCaptchaForm(request.POST or None) if show_captcha else None

    if request.method == 'POST':
        if 'resend' in request.POST:
            if len(attempts) >= max_attempts:
                error = 'Слишком много попыток. Попробуйте позже.'
            elif show_captcha and captcha_form and not captcha_form.is_valid():
                error = 'Подтвердите, что вы не робот.'
            elif seconds_left > 0:
                error = f'Повторная отправка будет доступна через {seconds_left} секунд.'
            else:
                code = str(random.randint(100000, 999999))
                data.update({
                    'code': code,
                    'last_code_sent': now,
                    'attempts': attempts + [now],
                })
                request.session[session_key] = data
                request.session.modified = True
                print(f"Saved code to session: {code}")  # Отладка

                try:
                    send_mail(
                        'Код для привязки Telegram',
                        f'Ваш код подтверждения: {code}',
                        None,
                        [request.user.email],
                        fail_silently=False,
                    )
                    message = 'Код отправлен на ваш email.'
                    TelegramChangeAttempt.objects.get_or_create(user=request.user)[0].increment()
                    print(f"Email sent to {request.user.email} with code: {code}")  # Отладка
                except Exception as e:
                    error = f'Ошибка при отправке письма: {e}'
                    print(f"Email sending error: {e}")  # Отладка

                seconds_left = settings.VERIFICATION_CODE_RESEND_TIMEOUT

        return render(request, 'lab_queue_app/telegram_link_code.html', {
            'email': request.user.email,
            'seconds_left': seconds_left,
            'resend_timeout': settings.VERIFICATION_CODE_RESEND_TIMEOUT,
            'show_captcha': show_captcha,
            'captcha_form': captcha_form,
            'error': error,
            'message': message,
        })

    return render(request, 'lab_queue_app/telegram_link_code.html', {
        'email': request.user.email,
        'seconds_left': seconds_left,
        'resend_timeout': settings.VERIFICATION_CODE_RESEND_TIMEOUT,
        'show_captcha': show_captcha,
        'captcha_form': captcha_form,
    })
@login_required
def telegram_link_verify(request):
    """Проверка кода и генерация deep link для привязки Telegram."""
    session_key = 'telegram_link_data'
    data = request.session.get(session_key, {})
    code = data.get('code', '')
    error = None

    print(f"Session data: {data}")  # Отладка: выводим данные сессии
    print(f"Stored code: {code}")  # Отладка: выводим сохранённый код

    if not code:
        messages.error(request, 'Код не был сгенерирован. Начните процесс заново.')
        print("No code in session, redirecting to telegram_link_request")  # Отладка
        return redirect('telegram_link_request')

    if request.method == 'POST':
        input_code = request.POST.get('code')
        print(f"Input code: {input_code}")  # Отладка: выводим введённый код
        if input_code != code:
            error = 'Неверный код.'
            print(f"Code mismatch: {input_code} != {code}")  # Отладка
        else:
            token = TelegramBindToken.objects.create(user=request.user)
            bot_username = 'plaki_plaki_prod_bot'
            deep_link = f"https://t.me/{bot_username}?start={token.token}"
            request.session.pop(session_key, None)  # Очищаем сессию
            TelegramChangeAttempt.objects.get_or_create(user=request.user)[0].reset()
            print(f"Generated deep link: {deep_link}")  # Отладка
            return render(request, 'lab_queue_app/register_telegram_link.html', {
                'deep_link': deep_link,
                'message': 'Нажмите кнопку ниже, чтобы привязать Telegram.'
            })

    return render(request, 'lab_queue_app/telegram_link_code.html', {
        'email': request.user.email,
        'seconds_left': 0,
        'resend_timeout': settings.VERIFICATION_CODE_RESEND_TIMEOUT,
        'show_captcha': False,
        'error': error,
    })

@login_required
def telegram_unlink_request(request):
    """Запрос кода для отвязки Telegram."""
    if not request.user.profile.telegram_id:
        messages.info(request, "Telegram не привязан.")
        return redirect('user_settings')

    now = int(timezone.now().timestamp())
    session_key = 'telegram_unlink_data'
    data = request.session.get(session_key, {
        'code': '',
        'last_code_sent': 0,
        'attempts': [],
    })

    seconds_left = max(0, data['last_code_sent'] + settings.VERIFICATION_CODE_RESEND_TIMEOUT - now)
    attempts = [t for t in data.get('attempts', []) if now - t < 600]
    show_captcha = len(attempts) >= 3
    max_attempts = 5
    error, message = None, None
    captcha_form = ResendCaptchaForm(request.POST or None) if show_captcha else None

    if request.method == 'POST':
        if 'resend' in request.POST:
            if len(attempts) >= max_attempts:
                error = 'Слишком много попыток. Попробуйте позже.'
            elif show_captcha and captcha_form and not captcha_form.is_valid():
                error = 'Подтвердите, что вы не робот.'
            elif seconds_left > 0:
                error = f'Повторная отправка будет доступна через {seconds_left} секунд.'
            else:
                code = str(random.randint(100000, 999999))
                data.update({
                    'code': code,
                    'last_code_sent': now,
                    'attempts': attempts + [now],
                })
                request.session[session_key] = data
                request.session.modified = True

                try:
                    send_mail(
                        'Код для отвязки Telegram',
                        f'Ваш код подтверждения: {code}',
                        None,
                        [request.user.email],
                        fail_silently=False,
                    )
                    message = 'Код отправлен на ваш email.'
                    TelegramChangeAttempt.objects.get_or_create(user=request.user)[0].increment()
                except Exception as e:
                    error = f'Ошибка при отправке письма: {e}'

                seconds_left = settings.VERIFICATION_CODE_RESEND_TIMEOUT

        return render(request, 'lab_queue_app/telegram_unlink_code.html', {
            'email': request.user.email,
            'seconds_left': seconds_left,
            'resend_timeout': settings.VERIFICATION_CODE_RESEND_TIMEOUT,
            'show_captcha': show_captcha,
            'captcha_form': captcha_form,
            'error': error,
            'message': message,
        })

    return render(request, 'lab_queue_app/telegram_unlink_code.html', {
        'email': request.user.email,
        'seconds_left': seconds_left,
        'resend_timeout': settings.VERIFICATION_CODE_RESEND_TIMEOUT,
        'show_captcha': show_captcha,
        'captcha_form': captcha_form,
    })

@login_required
def telegram_unlink_verify(request):
    """Проверка кода и отвязка Telegram."""
    session_key = 'telegram_unlink_data'
    data = request.session.get(session_key, {})
    code = data.get('code', '')
    error = None

    if not code:
        messages.error(request, 'Код не был сгенерирован. Начните процесс заново.')
        return redirect('telegram_unlink_request')

    if request.method == 'POST':
        input_code = request.POST.get('code')
        if input_code != code:
            error = 'Неверный код.'
        else:
            profile = request.user.profile
            profile.telegram_id = None
            profile.telegram_notifications = False
            profile.save()
            request.session.pop(session_key, None)
            TelegramChangeAttempt.objects.get_or_create(user=request.user)[0].reset()
            messages.success(request, "Telegram аккаунт успешно отвязан.")
            return redirect('user_settings')

    return render(request, 'lab_queue_app/telegram_unlink_code.html', {
        'email': request.user.email,
        'seconds_left': 0,
        'resend_timeout': settings.VERIFICATION_CODE_RESEND_TIMEOUT,
        'show_captcha': False,
        'error': error,
    })