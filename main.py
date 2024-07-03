import requests
import psycopg2

response = requests.get('https://api.hh.ru/areas')
areas = response.json()

# Поиск ID города по его названию
def get_city_id(city_name, areas):
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
            salary = 'Уровень дохода не указан'
        else:
            salary = str(item['salary']['to']) + ' ' + str(item['salary']['currency'])
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


# Основная функция
def main():
    keyword = "Python developer"
    area = 'Казань'
    number_of_vacancies = 10
    vacancies = parse_hh_api(get_city_id(area, areas), keyword, per_page=number_of_vacancies)

    if vacancies:
        save_to_db(vacancies)
        print(f"Saved {len(vacancies)} vacancies to the database.")
    else:
        print("No vacancies found or an error occurred.")


if __name__ == '__main__':
    main()
