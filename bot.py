import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
import re
from dotenv import load_dotenv

# ===== ЗАГРУЗКА .env =====
load_dotenv()

LOGIN = os.getenv("LOGIN")
PASSWORD = os.getenv("PASSWORD")
MESSAGE = "Здравствуйте! Я готов помочь вам с занятиями."
CHECK_INTERVAL = 60  # секунд между проверками
PROCESSED_REQUESTS_FILE = "processed_requests.txt"

def load_processed_requests():
    if not os.path.exists(PROCESSED_REQUESTS_FILE):
        return set()
    with open(PROCESSED_REQUESTS_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_processed_request(req_id: str):
    with open(PROCESSED_REQUESTS_FILE, "a", encoding="utf-8") as f:
        f.write(req_id + "\n")

def extract_request_id(card_element):
    """Ищем номер заявки внутри карточки"""
    text = card_element.text
    match = re.search(r"№\s*(\d+)", text)
    return match.group(1) if match else None

def init_driver():
    """Инициализация драйвера браузера"""
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # если нужен фоновый режим
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.maximize_window()
    return driver

def login(driver):
    """Функция авторизации"""
    try:
        driver.get("https://repetit.ru/lk/loginwithshortcode")
        wait = WebDriverWait(driver, 10)
        
        # Ищем div с текстом "Войти с логином и паролем"
        login_div = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(text(),'Воити с логином и паролем')]"))
        )
        login_div.click()
        
        # Поле "логин"
        login_input = wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='логин или номер телефона']"))
        )
        login_input.clear()
        login_input.send_keys(LOGIN)
        
        # Поле "пароль"
        password_input = driver.find_element(
            By.XPATH, "//input[@placeholder='пароль']"
        )
        password_input.clear()
        password_input.send_keys(PASSWORD)
        
        # Кнопка входа - ищем div с текстом "Войти"
        login_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "(//div[contains(text(),'Войти')])[1]"))
        )
        login_btn.click()
        
        # Ждем успешной авторизации
        time.sleep(5)
        print("Авторизация выполнена.")
        return True
        
    except Exception as e:
        print(f"Ошибка авторизации: {e}")
        return False



def find_math_requests(driver):
    """Находим заявки по математике через анализ содержимого"""
    math_requests = []
    
    try:
        # Ищем все элементы, которые содержат текст "Математика"
        # Используем XPath для поиска по тексту в любом вложенном элементе
        math_elements = driver.find_elements(
            By.XPATH, 
            "//*[contains(text(), 'Математика')]"
        )
        
        print(f"Найдено элементов с 'Математика': {len(math_elements)}")
        
        # Для каждого элемента с "Математика" ищем родительскую карточку
        for math_element in math_elements:
            try:
                # Ищем ближайший родительский div, который содержит всю карточку
                # Обычно это div с классом или несколько уровней вверх
                parent_card = math_element
                
                # Поднимаемся по DOM дереву, пока не найдем элемент, который выглядит как карточка
                for _ in range(10):  # максимум 10 уровней вверх
                    parent_card = parent_card.find_element(By.XPATH, "..")
                    
                    # Проверяем, что это похоже на карточку заявки
                    # Карточки обычно имеют определенные размеры и содержат несколько элементов
                    card_html = parent_card.get_attribute('innerHTML')
                    
                    # Если в карточке есть признаки заявки (цена, кнопки и т.д.)
                    if ('₽' in card_html or 'руб' in card_html) and len(card_html) > 500:
                        if parent_card not in math_requests:
                            math_requests.append(parent_card)
                        break
                        
            except Exception as e:
                print(f"Ошибка при поиске родительской карточки: {e}")
                continue
        
        # Альтернативный способ - ищем через структуру CSS классов
        if not math_requests:
            print("Пробуем альтернативный поиск через CSS селекторы...")
            
            # Ищем все div с классами, которые могут содержать карточки
            all_divs = driver.find_elements(By.TAG_NAME, "div")
            
            for div in all_divs:
                try:
                    div_text = div.text
                    div_html = div.get_attribute('innerHTML')
                    
                    # Проверяем, что div содержит "Математика" и похож на карточку заявки
                    if ('Математика' in div_text and 
                        ('₽' in div_text or 'руб' in div_text) and
                        len(div_html) > 300):
                        
                        if div not in math_requests:
                            math_requests.append(div)
                            
                except Exception as e:
                    continue
        
        print(f"Найдено карточек по математике: {len(math_requests)}")
        return math_requests
        
    except Exception as e:
        print(f"Ошибка при поиске заявок по математике: {e}")
        return []

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
    try:
        messages = driver.find_elements(
            By.CSS_SELECTOR, "div.css-146c3p1[dir='auto']"
        )
        for msg in messages:
            if message_text.strip() in msg.text.strip():
                return True
        return False
    except Exception as e:
        print(f"Ошибка при проверке сообщений: {e}")
        return False

def check_requests(driver):
    """Проверка и обработка заявок"""
    try:
        driver.get("https://repetit.ru/lk/teacher/neworders")
        time.sleep(3)
        
        # Проверяем, что страница загрузилась
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Находим заявки по математике
        math_requests = find_math_requests(driver)
        processed = load_processed_requests()
        
        if not math_requests:
            print("Заявки по математике не найдены.")
            return True
        
        for i, request_card in enumerate(math_requests):
            req_id = extract_request_id(request_card)

            if not req_id:
                print("Не удалось извлечь номер заявки, пропускаем")
                continue
            if req_id in processed:
                print(f"Заявка {req_id} уже обработана")
                continue

            try:
                print(f"Обрабатываем заявку по математике {i+1}/{len(math_requests)}")
                
                # Скроллим к карточке
                driver.execute_script("arguments[0].scrollIntoView(true);", request_card)
                time.sleep(1)
                
                # Кликаем на карточку
                driver.execute_script("arguments[0].click();", request_card)
                time.sleep(3)
                
                # Ищем div "Начать чат с клиентом"
                chat_div = find_chat_button(driver)
                
                if chat_div:
                    print("Найден элемент 'Начать чат с клиентом'")
                    driver.execute_script("arguments[0].click();", chat_div)
                    time.sleep(3)
                    
                    # Проверяем, было ли уже отправлено сообщение
                    already_sent = check_if_message_sent(driver, MESSAGE)
                    
                    if not already_sent:
                        print("Новая заявка найдена, но отправка сообщений отключена.")
                        
                        # Для отладки - выводим HTML страницы чата
                        print("=== DEBUG: Структура страницы чата ===")
                        try:
                            # Ищем текстовые поля разными способами
                            text_inputs = driver.find_elements(By.TAG_NAME, "textarea")
                            text_inputs += driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                            text_inputs += driver.find_elements(By.CSS_SELECTOR, "*[contenteditable='true']")
                            
                            print(f"Найдено полей для ввода: {len(text_inputs)}")
                            
                            for j, inp in enumerate(text_inputs):
                                print(f"Поле {j}: tag={inp.tag_name}, type={inp.get_attribute('type')}, "
                                      f"placeholder='{inp.get_attribute('placeholder')}'")
                                      
                        except Exception as debug_e:
                            print(f"Ошибка отладки: {debug_e}")
                        
                        # Раскомментируйте для активации отправки:
                        # try:
                        #     # Пробуем разные способы найти поле ввода
                        #     input_field = None
                        #     
                        #     # Способ 1: textarea
                        #     try:
                        #         input_field = driver.find_element(By.TAG_NAME, "textarea")
                        #     except NoSuchElementException:
                        #         pass
                        #     
                        #     # Способ 2: input type="text"
                        #     if not input_field:
                        #         try:
                        #             input_field = driver.find_element(By.CSS_SELECTOR, "input[type='text']")
                        #         except NoSuchElementException:
                        #             pass
                        #     
                        #     # Способ 3: contenteditable div
                        #     if not input_field:
                        #         try:
                        #             input_field = driver.find_element(By.CSS_SELECTOR, "*[contenteditable='true']")
                        #         except NoSuchElementException:
                        #             pass
                        #     
                        #     if input_field:
                        #         input_field.clear()
                        #         input_field.send_keys(MESSAGE)
                        #         input_field.send_keys(Keys.ENTER)
                        #         print("Сообщение отправлено.")
                        #     else:
                        #         print("Поле для ввода сообщения не найдено.")
                        #         
                        # except Exception as send_e:
                        #     print(f"Ошибка отправки сообщения: {send_e}")
                            
                    else:
                        print("Сообщение уже было отправлено.")
                        
                else:
                    print("Элемент 'Начать чат с клиентом' не найден.")
                    
                save_processed_request(req_id)
                processed.add(req_id)

                # Возвращаемся к списку заявок для обработки следующей
                driver.back()
                time.sleep(2)
                    
            except Exception as e:
                print(f"Ошибка при обработке заявки {i+1}: {e}")
                # Пробуем вернуться к списку заявок
                try:
                    driver.back()
                    time.sleep(2)
                except:
                    pass
                continue
                
    except Exception as e:
        print(f"Ошибка при проверке заявок: {e}")
        return False
    
    return True

def main():
    """Основная функция"""
    driver = None
    
    while True:
        try:
            # Инициализируем драйвер, если он не существует или закрыт
            if driver is None:
                driver = init_driver()
                if not login(driver):
                    print("Не удалось авторизоваться. Повтор через 30 секунд...")
                    time.sleep(30)
                    continue
            
            # Проверяем, что драйвер еще активен
            try:
                driver.current_url
            except WebDriverException:
                print("Драйвер потерял соединение. Переинициализация...")
                driver = None
                continue
            
            # Проверяем заявки
            if check_requests(driver):
                print(f"Ожидание {CHECK_INTERVAL} сек...")
                time.sleep(CHECK_INTERVAL)
            else:
                print("Ошибка при проверке заявок. Переинициализация через 30 сек...")
                if driver:
                    driver.quit()
                    driver = None
                time.sleep(30)
                
        except KeyboardInterrupt:
            print("Получен сигнал остановки...")
            break
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
            if driver:
                try:
                    driver.quit()
                except:
                    pass
                driver = None
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