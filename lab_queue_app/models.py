from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
import uuid
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction

class AvatarImage(models.Model):
    image = models.ImageField(upload_to='avatars/', validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Avatar uploaded at {self.uploaded_at}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    telegram_id = models.CharField(max_length=50, blank=True, null=True)
    let_in_hurry = models.BooleanField(default=False)
    can_hurry = models.BooleanField(default=True)
    avatar = models.ForeignKey(AvatarImage, on_delete=models.SET_NULL, blank=True, null=True, related_name='users')
    theme = models.CharField(max_length=50, default='light')
    email_notifications = models.BooleanField(default=True)
    telegram_notifications = models.BooleanField(default=False)

    def __str__(self):
        return f"Profile of {self.user.username}"

class StudyGroup(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Subject(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class PracticalWork(models.Model):
    name = models.CharField(max_length=100)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    ekurs_link = models.URLField(blank=True, null=True)
    sequence_number = models.IntegerField(unique=False)

    def __str__(self):
        return f"{self.name} (Subject: {self.subject.name})"

class Weekday(models.Model):
    name = models.CharField(max_length=20)
    short_name = models.CharField(max_length=3)
    order = models.IntegerField()

    def __str__(self):
        return self.name

class Schedule(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    start_time = models.TimeField()
    duration = models.IntegerField()
    weekday = models.ForeignKey(Weekday, on_delete=models.CASCADE)
    week_type = models.CharField(max_length=10, choices=[('even', 'Чётная'), ('odd', 'Нечётная'), ('both', 'Каждая')])

    def __str__(self):
        return f"{self.subject.name} on {self.weekday.name}"

class WaitingList(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    join_time = models.DateTimeField(auto_now_add=True)
    participant = models.ForeignKey(User, on_delete=models.CASCADE)
    list_position = models.IntegerField(default=0)

    def __str__(self):
        return f"Queue for {self.subject.name} (Pos: {self.list_position})"

class WaitingListParticipant(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    practical_work = models.ForeignKey(PracticalWork, on_delete=models.CASCADE)
    join_time = models.DateTimeField(auto_now_add=True)
    is_hurry = models.BooleanField(default=False)
    list_position = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('left', 'Left'), ('served', 'Served')], default='active')

    def __str__(self):
        return f"{self.user.username} in {self.practical_work.name}"

    @classmethod
    def recalculate_positions(cls, subject_id):
        """Пересчитывает позиции в очереди для всех активных участников."""
        # Получаем все активные записи для предмета
        participants = cls.objects.filter(
            practical_work__subject_id=subject_id,
            status='active'
        ).select_related('practical_work').order_by(
            'practical_work__sequence_number',  # Сначала по номеру лабораторной работы
            '-is_hurry',  # Затем по статусу "тороплюсь" (True идет первым)
            'join_time'  # Затем по времени входа
        )
        
        # Обновляем позиции одним запросом
        with transaction.atomic():
            for position, participant in enumerate(participants, 1):
                cls.objects.filter(id=participant.id).update(list_position=position)

# Сигналы для автоматического пересчёта позиций
@receiver(post_save, sender=WaitingListParticipant)
def update_positions_on_save(sender, instance, **kwargs):
    if instance.status == 'active' and not kwargs.get('update_fields'):
        WaitingListParticipant.recalculate_positions(instance.practical_work.subject_id)

@receiver(post_delete, sender=WaitingListParticipant)
def update_positions_on_delete(sender, instance, **kwargs):
    if instance.status == 'active':
        WaitingListParticipant.recalculate_positions(instance.practical_work.subject_id)

class UserStudyGroup(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    study_group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.username} in {self.study_group.name}"

class StudyGroupSubject(models.Model):
    study_group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.study_group.name} - {self.subject.name}"

class UserSubjectPreference(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    is_visible = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} preference for {self.subject.name}"

class TelegramBindToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='telegram_bind_tokens')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"Token {self.token} for {self.user.username}"