"""Фильтрация вакансий по пользовательским настройкам."""


def _is_missing(value):
    if value is None:
        return True
    text = str(value).strip()
    return not text or text.lower() == "не указан"


def _grade_base(value):
    normalized = str(value).replace("–", "-").strip()
    left = normalized.split("-", 1)[0].strip()
    return left.replace("+", "").strip().lower()


def filter_vacancies_for_user(vacancies, user_filters):
    """Фильтрует вакансии по grade/city/work_format/company из user.filters."""
    if not user_filters:
        return vacancies

    grades_filter = [str(v).strip().lower() for v in (user_filters.get("grades") or []) if str(v).strip()]
    cities_filter = [str(v).strip() for v in (user_filters.get("cities") or []) if str(v).strip()]
    work_formats_filter = [str(v).strip().lower() for v in (user_filters.get("work_formats") or []) if str(v).strip()]
    companies_filter = [str(v).strip() for v in (user_filters.get("companies") or []) if str(v).strip()]

    filtered = []
    for vacancy in vacancies:
        grade_ok = True
        city_ok = True
        work_format_ok = True
        company_ok = True

        grade = vacancy.get("grade")
        if grades_filter and not _is_missing(grade):
            grade_ok = _grade_base(grade) in grades_filter

        city = vacancy.get("city")
        if cities_filter and not _is_missing(city):
            city_ok = str(city).strip() in cities_filter

        work_format = vacancy.get("work_format")
        if work_formats_filter and not _is_missing(work_format):
            work_format_ok = str(work_format).strip().lower() in work_formats_filter

        company = vacancy.get("company")
        if companies_filter:
            company_ok = str(company).strip() in companies_filter

        if grade_ok and city_ok and work_format_ok and company_ok:
            filtered.append(vacancy)

    return filtered
