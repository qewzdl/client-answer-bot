import os
import time
import random
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from dotenv import load_dotenv
import sqlite3

# ===== ЗАГРУЗКА .env =====
load_dotenv()

LOGIN = os.getenv("LOGIN")
PASSWORD = os.getenv("PASSWORD")
MESSAGE = "Здравствуйте! Качественно и компетентно помогу справиться с вашей задачей. Первое занятие 60 минут со скидкой 50%, при записи до конца дня. Обо мне: образование МГУ, опыт работы более 15 лет с более чем 1000 учениками: индивидуально, на курсах, в школе, работа в качестве эксперта. Работаю на результат, при этом стремлюсь объяснить материал понятно и просто, что позволяет изменить отношение к предмету к лучшему. Провожу занятия через платформу Zoom, используя все доступные современные технологии. По запросу предоставляю записи занятий. Есть сотни положительных отзывов о моей работе, часть из них можно посмотреть на этой платформе"
CHECK_INTERVAL = 60 
DB_FILE = "processed_requests.db"
SPEED_FACTOR = 1
TYPING_SPEED_FACTOR = 4
CAN_SEND_MESSAGE = True

# ===== МАССИВ ПРЕДМЕТОВ ДЛЯ ПОИСКА =====
SUBJECTS_TO_SEARCH = [
    "Математика",
    "Обществознание",
]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_requests (
            id TEXT PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

def load_processed_requests():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id FROM processed_requests")
    rows = cur.fetchall()
    conn.close()
    return set(r[0] for r in rows)

def save_processed_request(req_id: str):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    try:
        cur.execute("INSERT OR IGNORE INTO processed_requests (id) VALUES (?)", (req_id,))
        conn.commit()
    finally:
        conn.close()

def extract_request_id(card_element):
    """Ищем номер заявки внутри карточки"""
    text = card_element.text
    match = re.search(r"№\s*(\d+)", text)
    return match.group(1) if match else None

def init_driver():
    """Инициализация драйвера браузера с улучшенными настройками"""
    chrome_options = Options()
    
    # Улучшенные опции для стабильности
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Увеличиваем таймауты
    chrome_options.add_argument("--page-load-strategy=normal")
    chrome_options.add_argument("--disable-web-security")
    
    # User-Agent для обхода детекции
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Устанавливаем таймауты
    driver.set_page_load_timeout(30)  # 30 сек на загрузку страницы
    driver.implicitly_wait(10)
    
    # Скрываем признаки автоматизации
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    driver.maximize_window()
    return driver

def safe_get(driver, url, max_retries=3):
    """Безопасная загрузка страницы с повторными попытками"""
    for attempt in range(max_retries):
        try:
            print(f"Загружаем {url} (попытка {attempt + 1}/{max_retries})")
            driver.get(url)
            
            # Ждем, пока страница загрузится
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Добавляем случайную задержку для имитации человеческого поведения
            time.sleep(random.uniform(2 / SPEED_FACTOR, 4 / SPEED_FACTOR))
            return True
            
        except TimeoutException:
            print(f"Таймаут при загрузке страницы (попытка {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(5 / SPEED_FACTOR)
                continue
        except WebDriverException as e:
            print(f"Ошибка WebDriver при загрузке: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 / SPEED_FACTOR)
                continue
        except Exception as e:
            print(f"Неожиданная ошибка при загрузке: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 / SPEED_FACTOR)
                continue
    
    print("Не удалось загрузить страницу после всех попыток")
    return False

def check_driver_health(driver):
    """Проверяем, что драйвер еще работает"""
    try:
        # Пытаемся получить текущий URL
        current_url = driver.current_url
        
        # Пытаемся выполнить простой JavaScript
        driver.execute_script("return document.readyState")
        
        return True
    except WebDriverException:
        return False
    except Exception:
        return False

def login(driver):
    """Функция авторизации напрямую через loginwithpassword"""
    try:
        if not safe_get(driver, "https://repetit.ru/lk/loginwithpassword"):
            return False

        wait = WebDriverWait(driver, 15)

        # Поле "логин"
        try:
            login_input = wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='логин или номер телефона']"))
            )
            login_input.clear()
            login_input.send_keys(LOGIN)
            time.sleep(1 / SPEED_FACTOR)
        except TimeoutException:
            print("Не найдено поле логина")
            return False

        # Поле "пароль"
        try:
            password_input = driver.find_element(
                By.XPATH, "//input[@placeholder='пароль']"
            )
            password_input.clear()
            password_input.send_keys(PASSWORD)
            time.sleep(1 / SPEED_FACTOR)
        except NoSuchElementException:
            print("Не найдено поле пароля")
            return False

        # Кнопка входа
        try:
            login_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, "(//div[contains(text(),'Войти')])[1]"))
            )
            login_btn.click()
        except TimeoutException:
            print("Не найдена кнопка входа")
            return False

        time.sleep(5 / SPEED_FACTOR)

        if "loginwithpassword" not in driver.current_url:
            print("Авторизация выполнена успешно.")
            return True
        else:
            print("Авторизация не удалась - остались на странице входа")
            return False

    except Exception as e:
        print(f"Ошибка авторизации: {e}")
        return False

def find_subject_requests(driver):
    """Находим заявки по всем указанным предметам"""
    subject_requests = []
    found_subjects = set()
    
    try:
        # Даем странице время загрузиться
        time.sleep(3)
        
        # Ищем элементы для каждого предмета из списка
        for subject in SUBJECTS_TO_SEARCH:
            try:
                subject_elements = driver.find_elements(
                    By.XPATH, 
                    f"//*[contains(text(), '{subject}')]"
                )
                
                if subject_elements:
                    print(f"Найдено элементов с '{subject}': {len(subject_elements)}")
                    found_subjects.add(subject)
                
                # Для каждого элемента с предметом ищем родительскую карточку
                for subject_element in subject_elements:
                    try:
                        # Ищем ближайший родительский div, который содержит всю карточку
                        parent_card = subject_element
                        
                        # Поднимаемся по DOM дереву, пока не найдем элемент, который выглядит как карточка
                        for _ in range(10):  # максимум 10 уровней вверх
                            parent_card = parent_card.find_element(By.XPATH, "..")
                            
                            # Проверяем, что это похоже на карточку заявки
                            card_html = parent_card.get_attribute('innerHTML')
                            
                            # Если в карточке есть признаки заявки (цена, кнопки и т.д.)
                            if ('₽' in card_html or 'руб' in card_html) and len(card_html) > 500:
                                if parent_card not in subject_requests:
                                    subject_requests.append(parent_card)
                                break
                                
                    except Exception as e:
                        continue
                        
            except Exception as e:
                print(f"Ошибка при поиске предмета '{subject}': {e}")
                continue
        
        # Альтернативный способ - ищем через структуру CSS классов
        if not subject_requests:
            print("Пробуем альтернативный поиск через CSS селекторы...")
            
            # Ищем все div с классами, которые могут содержать карточки
            all_divs = driver.find_elements(By.TAG_NAME, "div")
            
            for div in all_divs:
                try:
                    div_text = div.text
                    div_html = div.get_attribute('innerHTML')
                    
                    # Проверяем, содержит ли div любой из наших предметов
                    subject_found = False
                    for subject in SUBJECTS_TO_SEARCH:
                        if subject in div_text:
                            subject_found = True
                            found_subjects.add(subject)
                            break
                    
                    # Если найден предмет и div похож на карточку заявки
                    if (subject_found and 
                        ('₽' in div_text or 'руб' in div_text) and
                        len(div_html) > 300):
                        
                        if div not in subject_requests:
                            subject_requests.append(div)
                            
                except Exception as e:
                    continue
        
        if found_subjects:
            print(f"Найдены предметы: {', '.join(found_subjects)}")
        
        print(f"Всего найдено карточек с нужными предметами: {len(subject_requests)}")
        return subject_requests
        
    except Exception as e:
        print(f"Ошибка при поиске заявок по предметам: {e}")
        return []

def get_subject_from_card(card_element):
    """Определяет предмет из текста карточки"""
    try:
        card_text = card_element.text
        for subject in SUBJECTS_TO_SEARCH:
            if subject in card_text:
                return subject
        return "Неизвестный предмет"
    except:
        return "Неизвестный предмет"

def find_chat_button(driver):
    """Ищем div с текстом 'Начать чат с клиентом'"""
    try:
        # Ищем div с точным текстом
        chat_div = driver.find_element(
            By.XPATH, 
            "//div[contains(text(), 'Начать чат с клиентом')]"
        )
        return chat_div
        
    except NoSuchElementException:
        try:
            # Пробуем более широкий поиск
            chat_elements = driver.find_elements(
                By.XPATH, 
                "//*[contains(text(), 'чат') and contains(text(), 'клиент')]"
            )
            
            for element in chat_elements:
                if 'начать' in element.text.lower():
                    return element
                    
        except Exception as e:
            print(f"Ошибка поиска кнопки чата: {e}")
            
    return None

def check_if_message_sent(driver, message_text):
    """
    Простая и надежная проверка - есть ли сообщения в чате
    Если есть блок "Начните общение с клиентом" - значит чат пустой
    """
    try:
        # Даем время для загрузки чата
        time.sleep(2)
        
        # Ищем блок "Начните общение с клиентом"
        try:
            empty_chat_element = driver.find_element(
                By.XPATH, 
                "//*[contains(text(), 'Начните общение с клиентом')]"
            )
            
            if empty_chat_element:
                print("Чат пустой - найден блок 'Начните общение с клиентом'")
                return False  # Сообщения НЕ было отправлено
                
        except NoSuchElementException:
            # Если блока нет, значит в чате есть сообщения
            print("Блок 'Начните общение с клиентом' не найден - в чате есть сообщения")
            return True  # Сообщение УЖЕ было отправлено
            
        except Exception as e:
            print(f"Ошибка поиска блока пустого чата: {e}")
            
            # Если не можем найти блок пустого чата, используем запасной способ
            # Ищем любые сообщения в чате
            try:
                messages = driver.find_elements(By.CSS_SELECTOR, "div.css-146c3p1[dir='auto']")
                # Фильтруем служебные сообщения (время, даты и т.д.)
                actual_messages = []
                for msg in messages:
                    text = msg.text.strip()
                    # Игнорируем короткие сообщения (время), служебные тексты
                    if (len(text) > 5 and 
                        'Начните общение' not in text and
                        not re.match(r'^\d{1,2}:\d{2}$', text) and  # время типа 17:24
                        not re.match(r'^.{1,3},\s\d{1,2}\s\w+$', text)):  # дата типа "сб, 13 сентября"
                        actual_messages.append(text)
                
                if actual_messages:
                    print(f"В чате найдено {len(actual_messages)} сообщений")
                    return True  # Есть сообщения
                else:
                    print("В чате нет сообщений")
                    return False  # Нет сообщений
                    
            except Exception as e2:
                print(f"Ошибка запасного способа: {e2}")
                return False  # В случае ошибки считаем, что сообщения нет
        
    except Exception as e:
        print(f"Общая ошибка при проверке чата: {e}")
        return False

def process_single_request(driver, processed):
    """Обрабатывает одну заявку по любому из указанных предметов"""
    try:
        # Ищем заявки по всем предметам на текущей странице
        subject_requests = find_subject_requests(driver)
        
        if not subject_requests:
            return None, False  # Нет заявок для обработки
        
        # Обрабатываем только первую необработанную заявку
        for request_card in subject_requests:
            req_id = extract_request_id(request_card)
            
            if not req_id:
                print("Не удалось извлечь номер заявки, пропускаем")
                continue
                
            if req_id in processed:
                print(f"Заявка {req_id} уже обработана, пропускаем")
                continue
            
            # Определяем предмет заявки
            subject = get_subject_from_card(request_card)
            
            # Нашли необработанную заявку - обрабатываем её
            print(f"Обрабатываем заявку по предмету '{subject}' #{req_id}")
            
            try:
                # Скроллим к карточке
                driver.execute_script("arguments[0].scrollIntoView(true);", request_card)
                time.sleep(random.uniform(0.5  / SPEED_FACTOR, 1 / SPEED_FACTOR))
                
                # Кликаем на карточку
                driver.execute_script("arguments[0].click();", request_card)
                time.sleep(random.uniform(1 / SPEED_FACTOR, 2 / SPEED_FACTOR))
                
                # Ищем div "Начать чат с клиентом"
                chat_div = find_chat_button(driver)
                
                if chat_div:
                    print("Найден элемент 'Начать чат с клиентом'")
                    driver.execute_script("arguments[0].click();", chat_div)
                    time.sleep(random.uniform(1 / SPEED_FACTOR, 2 / SPEED_FACTOR))
                    
                    # Проверяем, было ли уже отправлено сообщение
                    already_sent = check_if_message_sent(driver, MESSAGE)
                    
                    if not already_sent:
                        print("Новая заявка найдена, отправляем сообщение.")
                        
                        try:
                            input_field = None
                            
                            # Пытаемся найти поле для ввода разными способами
                            wait = WebDriverWait(driver, 10)
                            
                            try:
                                input_field = wait.until(
                                    EC.element_to_be_clickable((By.TAG_NAME, "textarea"))
                                )
                            except TimeoutException:
                                # Пробуем другие селекторы
                                input_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], textarea, div[contenteditable='true']")
                                if input_fields:
                                    input_field = input_fields[-1]  # Берем последнее поле
                            
                            if input_field:
                                # Кликаем на поле и вводим текст
                                input_field.click()
                                time.sleep(1)
                                input_field.clear()
                                
                                # Вводим текст по символам для имитации человека
                                for char in MESSAGE:
                                    input_field.send_keys(char)
                                    time.sleep(random.uniform(0.25 / TYPING_SPEED_FACTOR, 0.5 / TYPING_SPEED_FACTOR))
                                
                                time.sleep(1)
                                # Отправляем сообщение
                                if CAN_SEND_MESSAGE:
                                    input_field.send_keys(Keys.ENTER)
                                    print("Сообщение отправлено.")
                                    
                                else:
                                    print("Отправка сообщений отключена.")
                                    
                            else:
                                print("Поле для ввода сообщения не найдено.")
                                
                        except Exception as send_e:
                            print(f"Ошибка отправки сообщения: {send_e}")
                            
                    else:
                        print("Сообщение уже было отправлено.")
                        
                else:
                    print("Элемент 'Начать чат с клиентом' не найден.")
                
                # Отмечаем заявку как обработанную
                save_processed_request(req_id)
                processed.add(req_id)
                
                return req_id, True  # Успешно обработали заявку
                
            except Exception as e:
                print(f"Ошибка при обработке заявки {req_id}: {e}")
                return req_id, False  # Ошибка при обработке
        
        # Все найденные заявки уже обработаны
        return None, True
        
    except Exception as e:
        print(f"Ошибка в process_single_request: {e}")
        return None, False

def check_requests(driver):
    """Проверка и обработка заявок с улучшенной обработкой ошибок"""
    try:
        processed = load_processed_requests()
        processed_in_session = 0
        max_requests_per_session = 10  # Максимум заявок за один цикл
        
        while processed_in_session < max_requests_per_session:
            # Проверяем здоровье драйвера перед каждой итерацией
            if not check_driver_health(driver):
                print("Драйвер потерял соединение во время обработки")
                return False
            
            # Загружаем страницу заново для каждой заявки
            if not safe_get(driver, "https://repetit.ru/lk/teacher/neworders"):
                print("Не удалось загрузить страницу заявок")
                return False
            
            # Обрабатываем одну заявку
            req_id, success = process_single_request(driver, processed)
            
            if req_id is None:
                # Нет новых заявок для обработки
                print("Все доступные заявки по указанным предметам обработаны.")
                break
            
            if success:
                processed_in_session += 1
                print(f"Заявка {req_id} успешно обработана. Обработано в этой сессии: {processed_in_session}")
                
                # Небольшая пауза между заявками
                time.sleep(random.uniform(3, 7))
            else:
                print(f"Ошибка при обработке заявки {req_id}")
                # При ошибке тоже делаем паузу
                time.sleep(5 / SPEED_FACTOR)
        
        if processed_in_session > 0:
            print(f"Сессия завершена. Обработано заявок: {processed_in_session}")
        else:
            print("Новых заявок по указанным предметам не найдено.")
            
    except Exception as e:
        print(f"Ошибка при проверке заявок: {e}")
        return False
    
    return True

def main():
    """Основная функция с улучшенным управлением драйвером"""
    print(f"Запуск скрипта для поиска заявок по предметам: {', '.join(SUBJECTS_TO_SEARCH)}")
    
    init_db()
    
    driver = None
    consecutive_failures = 0
    max_consecutive_failures = 3
    
    while True:
        try:
            # Инициализируем драйвер, если он не существует или закрыт
            if driver is None:
                print("Инициализируем новый драйвер...")
                driver = init_driver()
                
                if not login(driver):
                    print("Не удалось авторизоваться. Повтор через 30 секунд...")
                    if driver:
                        driver.quit()
                        driver = None
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        print(f"Слишком много неудачных попыток подряд ({consecutive_failures}). Увеличиваем паузу.")
                        time.sleep(300)  # 5 минут
                        consecutive_failures = 0
                    else:
                        time.sleep(30)
                    continue
            
            # Проверяем здоровье драйвера
            if not check_driver_health(driver):
                print("Драйвер потерял соединение. Переинициализация...")
                try:
                    driver.quit()
                except:
                    pass
                driver = None
                consecutive_failures += 1
                continue
            
            # Проверяем заявки
            if check_requests(driver):
                print(f"Проверка завершена успешно. Ожидание {CHECK_INTERVAL} сек...")
                consecutive_failures = 0  # Сбрасываем счетчик неудач
                time.sleep(CHECK_INTERVAL)
            else:
                print("Ошибка при проверке заявок. Переинициализация через 10 сек...")
                consecutive_failures += 1
                
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = None
                
                if consecutive_failures >= max_consecutive_failures:
                    print(f"Слишком много ошибок подряд ({consecutive_failures}). Длинная пауза.")
                    time.sleep(300)  # 5 минут
                    consecutive_failures = 0
                else:
                    time.sleep(10 / SPEED_FACTOR)
                
        except KeyboardInterrupt:
            print("Получен сигнал остановки...")
            break
        except Exception as e:
            print(f"Неожиданная ошибка в main: {e}")
            consecutive_failures += 1
            
            if driver:
                try:
                    driver.quit()
                except:
                    pass
                driver = None
                
            if consecutive_failures >= max_consecutive_failures:
                print(f"Критическое количество ошибок ({consecutive_failures}). Долгая пауза.")
                time.sleep(600)  # 10 минут
                consecutive_failures = 0
            else:
                time.sleep(30)
    
    # Закрываем драйвер при выходе
    if driver:
        try:
            driver.quit()
            print("Браузер закрыт.")
        except:
            pass

if __name__ == "__main__":
    main()