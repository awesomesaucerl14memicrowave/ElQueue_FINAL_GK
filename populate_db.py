import os
import django
from datetime import datetime, timedelta, time

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lab_queue.settings')
django.setup()

from lab_queue_app.models import StudyGroup, Subject, StudyGroupSubject, PracticalWork, Schedule, Weekday

def populate_db():
    print("Очистка базы данных...")
    StudyGroup.objects.all().delete()
    Subject.objects.all().delete()
    StudyGroupSubject.objects.all().delete()
    PracticalWork.objects.all().delete()
    Schedule.objects.all().delete()
    Weekday.objects.all().delete()

    # Создаём дни недели
    print("Создание дней недели...")
    weekdays = [
        ("Понедельник", "Пн", 0),
        ("Вторник", "Вт", 1),
        ("Среда", "Ср", 2),
        ("Четверг", "Чт", 3),
        ("Пятница", "Пт", 4),
        ("Суббота", "Сб", 5),
        ("Воскресенье", "Вс", 6),
    ]
    weekday_objects = []
    for name, short_name, order in weekdays:
        weekday = Weekday.objects.create(name=name, short_name=short_name, order=order)
        weekday_objects.append(weekday)
        print(f"Создан день недели: {name}")

    # Создаём учебные группы
    print("Создание учебных групп...")
    group1 = StudyGroup.objects.create(name="KI23-13")
    group2 = StudyGroup.objects.create(name="KI23-14")

    # Создаём предметы
    print("Создание предметов...")
    subjects = {
        "Физика": [group1],
        "Математика": [group1],
        "Химия": [group1],
        "Биология": [group2],
        "История": [group2],
        "Литература": [group2],
        "Информатика": [group1, group2],  # Общий предмет
    }

    subject_objects = {}
    for subject_name, groups in subjects.items():
        subject = Subject.objects.create(name=subject_name)
        subject_objects[subject_name] = subject
        for group in groups:
            StudyGroupSubject.objects.create(study_group=group, subject=subject)
        print(f"Создан предмет: {subject_name}, связан с группами: {[group.name for group in groups]}")

    # Создаём лабораторные работы с последовательным sequence_number
    print("Создание лабораторных работ...")
    sequence_number = 1  # Начальное значение для sequence_number
    for subject_name, subject in subject_objects.items():
        PracticalWork.objects.create(
            name=f"{subject_name} - Лабораторная 1",
            subject=subject,
            sequence_number=sequence_number,
            ekurs_link=f"https://ekurs.example.com/{subject_name.lower()}/lab1"
        )
        sequence_number += 1
        PracticalWork.objects.create(
            name=f"{subject_name} - Лабораторная 2",
            subject=subject,
            sequence_number=sequence_number,
            ekurs_link=f"https://ekurs.example.com/{subject_name.lower()}/lab2"
        )
        sequence_number += 1
        print(f"Созданы лабораторные работы для предмета: {subject_name} с sequence_number: {sequence_number-1} и {sequence_number}")

    # Создаём расписание
    print("Создание расписания...")
    base_time = time(10, 0)  # Начальное время: 10:00
    for idx, subject in enumerate(subject_objects.values()):
        # Первый слот
        start_time = (datetime.combine(datetime.today(), base_time) + timedelta(minutes=idx * 90)).time()
        Schedule.objects.create(
            subject=subject,
            start_time=start_time,
            duration=60,  # Длительность 60 минут
            weekday=weekday_objects[idx % 7],  # День недели циклически
            week_type="both"  # Каждую неделю
        )
        
        # Второй слот (через 2 дня)
        start_time = (datetime.combine(datetime.today(), base_time) + timedelta(minutes=(idx * 90 + 180))).time()
        Schedule.objects.create(
            subject=subject,
            start_time=start_time,
            duration=60,
            weekday=weekday_objects[(idx + 2) % 7],
            week_type="even"  # Чётная неделя
        )
        print(f"Создано расписание для предмета: {subject.name}")

    print("База данных успешно заполнена!")

if __name__ == "__main__":
    populate_db()