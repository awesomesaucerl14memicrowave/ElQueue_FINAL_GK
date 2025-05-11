from datetime import datetime, timedelta, time

def get_academic_week_number(current_datetime=None):
    if current_datetime is None:
        current_datetime = datetime.now()
    year = current_datetime.year
    start_of_academic_year = datetime(year, 9, 1)
    if current_datetime < start_of_academic_year:
        start_of_academic_year = datetime(year - 1, 9, 1)
    delta = current_datetime - start_of_academic_year
    weeks_since_start = delta.days // 7
    return weeks_since_start % 2

def get_schedule_info(slot, current_datetime=None):
    if current_datetime is None:
        current_datetime = datetime.now()

    # Чётность текущей академической недели
    current_week_number = get_academic_week_number(current_datetime)
    is_current_week_even = current_week_number % 2 == 0
    slot_week_type = slot.week_type.lower()
    is_slot_week_even = slot_week_type == 'even'

    # День недели из расписания
    slot_weekday = slot.weekday.name.lower()
    weekday_map = {
        'понедельник': 0, 'вторник': 1, 'среда': 2, 'четверг': 3,
        'пятница': 4, 'суббота': 5, 'воскресенье': 6
    }
    slot_weekday_num = weekday_map[slot_weekday]
    current_weekday_num = current_datetime.weekday()

    # Разница в днях до следующего дня недели
    days_until_next = (slot_weekday_num - current_weekday_num) % 7
    if days_until_next == 0:
        start_datetime = datetime.combine(current_datetime.date(), slot.start_time)
        end_datetime = start_datetime + timedelta(minutes=slot.duration)
        if current_datetime > end_datetime:
            days_until_next = 7

    # Базовая дата следующей пары
    next_date = current_datetime.date() + timedelta(days=days_until_next)

    # Корректируем чётность
    next_datetime = datetime.combine(next_date, slot.start_time)
    next_week_number = get_academic_week_number(next_datetime)
    is_next_week_even = next_week_number % 2 == 0

    if is_next_week_even != is_slot_week_even:
        next_date += timedelta(days=7)

    # Проверяем, идёт ли пара сейчас
    is_running = False
    if days_until_next == 0:
        start_datetime = datetime.combine(current_datetime.date(), slot.start_time)
        end_datetime = start_datetime + timedelta(minutes=slot.duration)
        is_running = start_datetime <= current_datetime <= end_datetime

    # Формируем текст расписания
    start_time_str = slot.start_time.strftime("%H:%M")
    end_time_str = (datetime.combine(current_datetime.date(), slot.start_time) + 
                    timedelta(minutes=slot.duration)).strftime("%H:%M")
    week_type_display = 'Чётная' if slot.week_type == 'even' else 'Нечётная' if slot.week_type == 'odd' else 'Каждая'
    schedule_text = f"{slot.weekday.name} ({week_type_display} неделя) {start_time_str}-{end_time_str}"

    return {
        'schedule_text': schedule_text,
        'next_date': next_date.strftime("%d.%m.%Y"),
        'is_running': is_running
    }