from django.contrib.auth.models import User
from .models import WaitingListParticipant, PracticalWork
from django.shortcuts import get_object_or_404
from django.db import transaction
from .services.notifications import notification_service

def join_queue_util(user, work_id, is_hurry=False):
    """
    Добавляет пользователя в очередь на указанную лабораторную работу.
    Возвращает True при успехе, False если уже в очереди.
    """
    work = get_object_or_404(PracticalWork, id=work_id)
    
    # Проверяем, не стоит ли пользователь уже в очереди
    existing_participant = WaitingListParticipant.objects.filter(
        user=user,
        practical_work=work,
        status='active'
    ).first()
    
    if existing_participant:
        return False, "Вы уже стоите в этой очереди"
    
    # Проверяем, не сдана ли уже эта работа
    served_participant = WaitingListParticipant.objects.filter(
        user=user,
        practical_work=work,
        status='served'
    ).first()
    
    if served_participant:
        return False, "Вы уже сдали эту работу"
    
    with transaction.atomic():
        # Создаем нового участника очереди
        participant = WaitingListParticipant.objects.create(
            user=user,
            practical_work=work,
            is_hurry=is_hurry,
            status='active'
        )
        
        # Уведомляем пользователя о вступлении в очередь
        notification_service.notify_queue_join_leave(
            user=user,
            action='join',
            queue_name=f"{work.subject.name} - {work.name}"
        )
        
        return True, "Вы успешно добавлены в очередь"

def leave_queue_util(user, work_id, has_passed=False):
    """Удаление пользователя из очереди"""
    work = get_object_or_404(PracticalWork, id=work_id)
    participant = get_object_or_404(
        WaitingListParticipant,
        user=user,
        practical_work=work,
        status='active'
    )
    
    old_position = participant.list_position
    
    with transaction.atomic():
        if has_passed:
            participant.status = 'served'
        else:
            participant.status = 'inactive'
        participant.save()
        
        # Получаем всех активных участников для этой работы
        active_participants = WaitingListParticipant.objects.filter(
            practical_work=work,
            status='active'
        ).order_by('join_time')
        
        # Обновляем позиции для оставшихся участников
        for i, p in enumerate(active_participants, 1):
            if p.list_position != i:
                old_pos = p.list_position
                p.list_position = i
                p.save()
                
                # Уведомляем об изменении позиции
                notification_service.notify_position_change(
                    user=p.user,
                    queue_name=f"{work.subject.name} - {work.name}",
                    new_position=i,
                    old_position=old_pos
                )
                
                # Уведомляем о достижении определенных позиций
                if i in [1, 2, 3]:
                    notification_service.notify_position_milestone(
                        user=p.user,
                        queue_name=f"{work.subject.name} - {work.name}",
                        position=i
                    )
        
        # Уведомляем пользователя о выходе из очереди
        notification_service.notify_queue_join_leave(
            user=user,
            action='leave',
            queue_name=f"{work.subject.name} - {work.name}"
        )
        
        return True, "Вы успешно покинули очередь"

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