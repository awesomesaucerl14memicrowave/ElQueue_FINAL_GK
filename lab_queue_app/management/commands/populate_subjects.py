from django.core.management.base import BaseCommand
from lab_queue_app.models import Subject, PracticalWork, StudyGroup, StudyGroupSubject
from datetime import datetime

class Command(BaseCommand):
    help = 'Populate database with subjects and practical works'

    def handle(self, *args, **options):
        # Очищаем существующие данные
        PracticalWork.objects.all().delete()
        StudyGroupSubject.objects.all().delete()
        Subject.objects.all().delete()

        # Базы данных
        db_subject, _ = Subject.objects.get_or_create(name="Базы данных")
        db_works = [
            ("Практическая работа 1. Информационная модель торговой компании.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609153", None, 1),
            ("Практическая работа 2. ER модель базы данных торговой компании.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609154", None, 2),
            ("Практическая работа 3. Реализация БД в SQL Server Management Studio.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609155", None, 3),
            ("Практическая работа 4. Стандартные функции.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609156", None, 4),
            ("Практическая работа 5. Выборки и проекции.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609157", None, 5),
            ("Практическая работа 6. Подзапросы.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609158", None, 6),
            ("Практическая работа 7. Соединение таблиц.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609159", None, 7),
            ("Практическая работа 8 часть 1. Группировка данных.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609160", None, 8),
            ("Практическая работа 8 часть 2. Оконные функции.", "https://e.sfu-kras.ru/mod/assign/view.php?id=1134959", None, 9),
            ("Практическая работа 9. Определение данных.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609161", None, 10),
            ("Практическая работа 10. Модификация данных.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609162", None, 11),
            ("Практическая работа 11. Хранимые процедуры. Пользовательские функции.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609163", None, 12),
            ("Практическая работа 12. Представления.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609164", None, 13),
            ("Практическая работа 13. Триггеры.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609165", None, 14),
            ("Итоговая контрольная работа.", "https://e.sfu-kras.ru/mod/assign/view.php?id=609167", None, 15),
        ]

        # КСП
        ksp_subject, _ = Subject.objects.get_or_create(name="Клиент-серверное программирование")
        ksp_works = [
            ("Задание 7 - Django: Создание формы ввода данных.", "https://e.sfu-kras.ru/mod/assign/view.php?id=1207811", None, 1),
            ("Задание 8 - Django: Модели и формы.", "https://e.sfu-kras.ru/mod/assign/view.php?id=1207812", None, 2),
            ("Задание 9 - Создание многостраничного приложения.", "https://e.sfu-kras.ru/mod/assign/view.php?id=1346042", None, 3),
            ("Задание 10 - Frontend-функционал на JavaScript.", "https://e.sfu-kras.ru/mod/assign/view.php?id=1156919", None, 4),
            ("Задание 11 - Асинхронные запросы (AJAX).", "https://e.sfu-kras.ru/mod/assign/view.php?id=1156923", None, 5),
            ("Задание 12 - AJAX-запросы с использованием Deferred-объектов.", "https://e.sfu-kras.ru/mod/assign/view.php?id=1207813", None, 6),
        ]

        # МИСОИ
        misoi_subject, _ = Subject.objects.get_or_create(name="Методы и средства отображения информации")
        misoi_works = [
            ("ПЗ 1. Числовые данные и их подготовка.", "https://e.sfu-kras.ru/mod/assign/view.php?id=699464", "2025-02-20", 1),
            ("ПЗ 2. Одно- и двухмерная визуализация.", "https://e.sfu-kras.ru/mod/assign/view.php?id=1137030", "2025-03-06", 2),
            ("ПЗ 3. Иерархические и сетевые данные.", "https://e.sfu-kras.ru/mod/assign/view.php?id=1145066", "2025-03-27", 3),
            ("ПЗ 4. Визуализация многомерных данных.", "https://e.sfu-kras.ru/mod/assign/view.php?id=1155236", "2025-04-17", 4),
            ("ПЗ 5. Оценка визуального представления.", None, "2025-05-22", 5),
            ("ПЗ 6. Инфографика.", "https://e.sfu-kras.ru/mod/assign/view.php?id=699465", None, 6),
            ("ПЗ 7. Создание визуальных представлений с использованием ИИ-сервисовЗадание.", "https://e.sfu-kras.ru/mod/assign/view.php?id=1900292", "2025-05-29", 7),
        ]

        # ГИС
        gis_subject, _ = Subject.objects.get_or_create(name="Разработка ПО ГИС")
        gis_works = [
            ("ПР 1. Установка и изучение интерфейса QGIS", "https://e.sfu-kras.ru/mod/assign/view.php?id=1880045", None, 1),
            ("ПР 2. Операции пространственного анализа в QGIS и Jupyter Notebook/JupyterLab", "https://e.sfu-kras.ru/mod/assign/view.php?id=1880157", None, 2),
            ("ПР 3. Обработка векторных данных в формате MIF/MID на PythonЗ", "https://e.sfu-kras.ru/mod/assign/view.php?id=1880158", None, 3),
            ("ПР 4. Построение кратчайшего маршрута", "https://e.sfu-kras.ru/mod/assign/view.php?id=1880167", None, 4),
            ("ПР 5. Обработка спутниковых данных", "https://e.sfu-kras.ru/mod/assign/view.php?id=1880168", None, 5),
            ("ПР 6. Обработка растровых пространственных данных", "https://e.sfu-kras.ru/mod/assign/view.php?id=1880169", None, 6),
            ("ПР 7. Построение цифровой модели рельефа в 3D", "https://e.sfu-kras.ru/mod/assign/view.php?id=1908313", None, 7),
            ("ПР 8. Создание пространственной базы данных", None, None, 8),
            ("ПР 9. Создание модели обработки данных", "https://e.sfu-kras.ru/mod/assign/view.php?id=1880172", None, 9),
        ]

        # ТП
        tp_subject, _ = Subject.objects.get_or_create(name="Технологии программирования")
        tp_works = [
            ("Практическая 1. базовый синтаксис языка python.", "https://e.sfu-kras.ru/mod/assign/view.php?id=619629", "2025-02-24", 1),
            ("Практическая 2. Основы функционального программирования.", "https://e.sfu-kras.ru/mod/assign/view.php?id=619632", "2025-03-15", 2),
            ("Практическая 3. Объектно-ориентированное программирование.", "https://e.sfu-kras.ru/mod/assign/view.php?id=619633", "2025-03-29", 3),
            ("Практическая 4. Параллельное программирование.", "https://e.sfu-kras.ru/mod/assign/view.php?id=619634", "2025-04-15", 4),
            ("Практическая 5. Асинхронное программирование.", "https://e.sfu-kras.ru/mod/assign/view.php?id=747663", "2025-05-15", 5),
            ("Практическая 6. Создание веб-приложения на Django.", "https://e.sfu-kras.ru/mod/assign/view.php?id=651154", "2025-05-15", 6),
        ]

        # Создаем работы для каждого предмета
        for name, link, deadline, seq in db_works:
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date() if deadline else None
            PracticalWork.objects.create(
                name=name,
                subject=db_subject,
                ekurs_link=link,
                sequence_number=seq,
                deadline=deadline_date
            )

        for name, link, deadline, seq in ksp_works:
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date() if deadline else None
            PracticalWork.objects.create(
                name=name,
                subject=ksp_subject,
                ekurs_link=link,
                sequence_number=seq,
                deadline=deadline_date
            )

        for name, link, deadline, seq in misoi_works:
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date() if deadline else None
            PracticalWork.objects.create(
                name=name,
                subject=misoi_subject,
                ekurs_link=link,
                sequence_number=seq,
                deadline=deadline_date
            )

        for name, link, deadline, seq in gis_works:
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date() if deadline else None
            PracticalWork.objects.create(
                name=name,
                subject=gis_subject,
                ekurs_link=link,
                sequence_number=seq,
                deadline=deadline_date
            )

        for name, link, deadline, seq in tp_works:
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date() if deadline else None
            PracticalWork.objects.create(
                name=name,
                subject=tp_subject,
                ekurs_link=link,
                sequence_number=seq,
                deadline=deadline_date
            )

        # Связываем предметы с учебными группами
        subjects = [db_subject, ksp_subject, misoi_subject, gis_subject, tp_subject]
        study_groups = StudyGroup.objects.all()
        
        for study_group in study_groups:
            for subject in subjects:
                StudyGroupSubject.objects.get_or_create(
                    study_group=study_group,
                    subject=subject
                )

        self.stdout.write(self.style.SUCCESS('Successfully populated database with subjects and works')) 