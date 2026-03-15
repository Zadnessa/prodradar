"""Фильтрация вакансий по пользовательским настройкам."""


def _is_missing(value):
    if value is None:
        return True
    text = str(value).strip()
    return not text or text.lower() == "не указан"


def _grade_base(value):
    normalized = str(value).replace("–", "-").strip()
    left = normalized.split("-", 1)[0].strip()
    return left.strip().lower()






def _grade_candidates(value):
    normalized = str(value).replace("–", "-").strip()
    raw_parts = [part.strip() for part in normalized.split("-") if part.strip()]
    if not raw_parts:
        raw_parts = [normalized]
    return {_grade_base(part) for part in raw_parts if part}

def _expand_grade_filters(grades_filter):
    expanded = set(grades_filter)
    if "junior" in expanded:
        expanded.add("junior+")
    if "middle" in expanded:
        expanded.add("middle+")
    if "senior" in expanded:
        expanded.add("senior+")
    return list(expanded)

def filter_vacancies_for_user(vacancies, user_filters):
    """Фильтрует вакансии по grade/city/work_format/company из user.filters."""
    if not user_filters:
        return vacancies

    grades_filter = [str(v).strip().lower() for v in (user_filters.get("grades") or []) if str(v).strip()]
    grades_filter = _expand_grade_filters(grades_filter)
    grades_filter_set = set(grades_filter)
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
            grade_parts = [part.strip() for part in str(grade).split(",") if part.strip()]
            if not grade_parts:
                grade_parts = [str(grade).strip()]
            grade_ok = any(_grade_candidates(part) & grades_filter_set for part in grade_parts)

        city = vacancy.get("city")
        if cities_filter and not _is_missing(city):
            city_value = str(city).strip()
            if city_value == "Любой город":
                city_ok = True
            else:
                city_parts = [part.strip() for part in city_value.split(",") if part.strip()]
                city_ok = any(part in cities_filter for part in city_parts)

        work_format = vacancy.get("work_format")
        if work_formats_filter and not _is_missing(work_format):
            work_format_parts = [part.strip().lower() for part in str(work_format).split(",") if part.strip()]
            work_format_ok = any(part in work_formats_filter for part in work_format_parts)

        company = vacancy.get("company")
        if companies_filter:
            company_ok = str(company).strip() in companies_filter

        if grade_ok and city_ok and work_format_ok and company_ok:
            filtered.append(vacancy)

    return filtered
