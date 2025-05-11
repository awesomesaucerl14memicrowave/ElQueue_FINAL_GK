from django.contrib import admin
from .models import UserProfile, StudyGroup, Subject, PracticalWork, Weekday, Schedule, WaitingList, WaitingListParticipant, UserStudyGroup, StudyGroupSubject, UserSubjectPreference, AvatarImage

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