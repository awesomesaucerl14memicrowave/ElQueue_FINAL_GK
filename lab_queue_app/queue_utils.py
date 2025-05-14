from django.contrib.auth.models import User
from .models import WaitingListParticipant, PracticalWork

def join_queue_util(user, work_id, is_hurry=False):
    """
    Добавляет пользователя в очередь на указанную лабораторную работу.
    Возвращает True при успехе, False если уже в очереди.
    """
    # Явно разрешаем SimpleLazyObject
    user_id = user.id if hasattr(user, 'id') else user.pk
    practical_work = PracticalWork.objects.get(id=work_id)
    # Проверяем, есть ли уже активная очередь по этому предмету
    existing = WaitingListParticipant.objects.filter(
        user_id=user_id,
        practical_work__subject=practical_work.subject,
        status='active'
    ).exists()
    if existing:
        return False

    # Создаём запись в очереди
    participant = WaitingListParticipant.objects.create(
        user_id=user_id,
        practical_work=practical_work,
        is_hurry=is_hurry,
        status='active'
    )
    WaitingListParticipant.recalculate_positions(practical_work.subject_id)
    return True

def leave_queue_util(user, work_id, has_passed=False):
    print("Leave queue - User:", user, type(user), "User ID:", user.id if hasattr(user, 'id') else None)  # Отладка
    user_id = user.id if hasattr(user, 'id') else user.pk
    practical_work = PracticalWork.objects.get(id=work_id)
    participant = WaitingListParticipant.objects.filter(
        user_id=user_id,
        practical_work=practical_work,
        status='active'
    ).first()
    if participant:
        if has_passed:
            participant.status = 'served'
            participant.save()
            WaitingListParticipant.recalculate_positions(practical_work.subject_id)
        else:
            participant.delete()

def recalculate_positions(subject_id):
    """
    Пересчитывает позиции в очереди для указанного предмета.
    """
    participants = WaitingListParticipant.objects.filter(
        practical_work__subject_id=subject_id,
        status='active'
    ).order_by('-is_hurry', 'join_time')
    for idx, participant in enumerate(participants, 1):
        participant.list_position = idx
        participant.save(update_fields=['list_position'])