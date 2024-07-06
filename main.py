import requests
import psycopg2
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters

# Получение данных о регионах и городах
response = requests.get('https://api.hh.ru/areas')
areas = response.json()

# Поиск ID города по его названию
def get_city_id(city_name, areas):
    if city_name.lower() in ['москва', 'зеленоград']:
        return 1
    for country in areas:
        for area in country['areas']:
            for city in area['areas']:
                if city['name'].lower() == city_name.lower():
                    return city['id']
    return None

# Функция для получения вакансий через API HH.ru
def parse_hh_api(area, keyword, page=0, per_page=100):
    url = "https://api.hh.ru/vacancies"
    params = {
        'area': area,
        'text': keyword,
        'page': page,
        'per_page': per_page
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        print(f"Failed to retrieve data: {response.status_code}")
        return []

    data = response.json()
    vacancies = []
    for item in data['items']:
        title = item['name']
        link = item['alternate_url']
        company = item['employer']['name']
        area = item['area']['name']
        if item['salary'] is None:
            salary = None
        else:
            salary = item['salary']['to']
        description = item.get('snippet', {}).get('responsibility', 'No description available')

        vacancies.append({
            'title': title,
            'link': link,
            'company': company,
            'area': area,
            'salary': salary,
            'description': description
        })

    return vacancies

# Функция для сохранения вакансий в базу данных
def save_to_db(vacancies):
    conn = psycopg2.connect(
        host="localhost",
        database="job_parser",
        user="postgres",
        password="erjgi58fl8iflu"
    )
    cursor = conn.cursor()

	# Проверка на существование таблицы и её создание, если она не существует
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vacancies (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255),
            link TEXT UNIQUE,
            company VARCHAR(255),
            area VARCHAR(255),
            salary VARCHAR(255),
            description TEXT
        )
    """)
	
    for vacancy in vacancies:
        cursor.execute("""
                SELECT 1 FROM vacancies WHERE link = %s
            """, (vacancy['link'],))

        if cursor.fetchone() is None:
            cursor.execute("""
                    INSERT INTO vacancies (title, link, company, area, salary, description) VALUES (%s, %s, %s, %s, %s, %s)
                """, (vacancy['title'], vacancy['link'], vacancy['company'], vacancy['area'], vacancy['salary'], vacancy['description']))
    conn.commit()
    cursor.close()
    conn.close()

# Основная функция для поиска вакансий
def find_vacancies(city_name, keyword, number_of_vacancies, min_salary=None, description_keyword=None):
    city_id = get_city_id(city_name, areas)
    if city_id is None:
        return f"Город {city_name} не найден."
    vacancies = parse_hh_api(city_id, keyword, per_page=100)

    if not vacancies:
        return "Вакансий не найдено или произошла ошибка."

    # Фильтрация вакансий по зарплате и ключевому слову в описании
    filtered_vacancies = []
    for vacancy in vacancies:
        if vacancy['salary'] is None or vacancy['description'] is None:
            continue
        if min_salary is not None and vacancy['salary'] is not None and int(vacancy['salary']) < int(min_salary):
            continue
        if description_keyword is not None and description_keyword.lower() not in vacancy['description'].lower():
            continue
        filtered_vacancies.append(vacancy)

    if len(filtered_vacancies) > number_of_vacancies:
        filtered_vacancies = filtered_vacancies[:number_of_vacancies]

    if filtered_vacancies:
        return filtered_vacancies
    else:
        return "Вакансий не найдено по указанным критериям."

# Телеграм-бот
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Привет! Введите город, ключевое слово для поиска вакансий, количество вакансий, минимальную зарплату и ключевое слово для описания в формате: город, ключевое слово, количество, минимальная зарплата, ключевое слово для описания')

def handle_message(update: Update, context: CallbackContext) -> None:
    text = update.message.text
    try:
        parts = text.split(',')
        if len(parts) == 3:
            city_name, keyword, number_of_vacancies = parts
            min_salary = None
            description_keyword = None
        elif len(parts) == 4:
            city_name, keyword, number_of_vacancies, min_salary = parts
            description_keyword = None
        elif len(parts) == 5:
            city_name, keyword, number_of_vacancies, min_salary, description_keyword = parts
        else:
            update.message.reply_text('Неправильный формат. Используйте: город, ключевое слово, количество, минимальная зарплата, ключевое слово для описания')
            return

        city_name = city_name.strip()
        keyword = keyword.strip()
        number_of_vacancies = int(number_of_vacancies.strip())
        if min_salary is not None:
            min_salary = int(min_salary.strip())
        if description_keyword is not None:
            description_keyword = description_keyword.strip()

        vacancies = find_vacancies(city_name, keyword, number_of_vacancies, min_salary, description_keyword)
        if isinstance(vacancies, str):
            update.message.reply_text(vacancies)
        else:
            for vacancy in vacancies:
                vacancy_info = f"Название: {vacancy['title']}\nКомпания: {vacancy['company']}\nГород: {vacancy['area']}\nЗарплата: {vacancy['salary']}\nСсылка: {vacancy['link']}\nОписание: {vacancy['description']}"
                update.message.reply_text(vacancy_info)
    except ValueError:
        update.message.reply_text('Неправильный формат. Используйте: город, ключевое слово, количество, минимальная зарплата, ключевое слово для описания')

def main():
    updater = Updater("7334197997:AAEmpt_czMuguFUADxbVDq8kas6Cn0uw3EU")
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
