from django.contrib import admin
from .models import EmailChangeAttempt, UserProfile, StudyGroup, Subject, PracticalWork, Weekday, Schedule, WaitingList, WaitingListParticipant, UserStudyGroup, StudyGroupSubject, UserSubjectPreference, AvatarImage

admin.site.register(UserProfile)
admin.site.register(StudyGroup)
admin.site.register(Subject)
admin.site.register(PracticalWork)
admin.site.register(Weekday)
admin.site.register(Schedule)
admin.site.register(WaitingList)
admin.site.register(WaitingListParticipant)
admin.site.register(UserStudyGroup)
admin.site.register(StudyGroupSubject)
admin.site.register(UserSubjectPreference)
admin.site.register(AvatarImage)

@admin.register(EmailChangeAttempt)
class EmailChangeAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'resend_count', 'last_sent')
    search_fields = ('user__username', 'user__email')
    actions = ['reset_attempts']

    def reset_attempts(self, request, queryset):
        updated = queryset.update(resend_count=0)
        self.message_user(request, f"Сброслено попыток для {updated} записи(ей).")
    reset_attempts.short_description = "Сбросить количество попыток подтверждения email"

@admin.action(description='Сбросить попытки смены почты')
def reset_email_attempts(modeladmin, request, queryset):
    for user in queryset:
        session_key = f'_auth_user_id_{user.id}_email_change_data'
        if session_key in request.session:
            del request.session[session_key]

admin.site.add_action(reset_email_attempts)