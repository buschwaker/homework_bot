import os
import sys
import time
import requests
import telegram
from dotenv import load_dotenv
import logging
from classes_to_except import NonCritical, CriticalErrors

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(
    logging.Formatter(fmt='[%(asctime)s: %(levelname)s] %(message)s')
)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except TypeError:
        logger.error('Сообщение не удалось послать!')
    else:
        logger.info('Сообщение успешно отправлено!')


def get_api_answer(current_timestamp):
    """Запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
    except Exception:
        raise CriticalErrors('Ошибка доступа к эндпоинту!')
    else:
        if homework_statuses.status_code == 200:
            return homework_statuses.json()
        else:
            raise CriticalErrors(
                f'Код страницы: {homework_statuses.status_code}!'
            )


def check_response(response):
    """Проверка API на корректность."""
    if type(response) == list:
        response = response[0]
    if 'homeworks' in response:
        if type(response.get('homeworks')) != list:
            raise CriticalErrors('Неизвестное форматирование ответа!')
        if len(response.get('homeworks')) == 0:
            raise NonCritical('Домашка без изменений!')
        return response.get('homeworks')
    else:
        raise CriticalErrors('Нет homeworks в ключах ответа!')


def parse_status(homework):
    """Извлечение статуса из информации о домашнем задании."""
    if type(homework) == list:
        homework = homework[0]
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка обязательных переменных окружения."""
    if (
        PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
        or TELEGRAM_CHAT_ID is None
    ):
        logger.critical('Отсутствие обязательных переменных окружения!')
        return False
    else:
        return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    list_errors_occurred = []
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
        except NonCritical as debug:
            logger.debug(debug)
        except CriticalErrors as error:
            logger.error(error)
            list_errors_occurred.append(str(error))
            list_last_index = len(list_errors_occurred) - 1
            # отправляется сообщение при условии, что не было зафиксировано
            # 2 одинаковые ошибки подряд в текущей сессии
            if len(list_errors_occurred) == 1 or (
                    list_errors_occurred[list_last_index]
                    != list_errors_occurred[list_last_index - 1]
            ):
                send_message(bot, str(error))
        else:
            send_message(bot, message)
        finally:
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
