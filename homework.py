import os
import sys
import time
import requests
import telegram
from dotenv import load_dotenv
import logging
from classes_to_except import NonCritical, CriticalErrors, KeyNotFoundError
from telegram.error import RetryAfter, TimedOut


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
    except (RetryAfter, TimedOut):
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
    except requests.exceptions.MissingSchema:
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
    global current_date
    if isinstance(response, list):
        response = response[0]
    # временная точка, которая на следующей итерации при отсутвии ошибок
    # CriticalErrors будет передана в качестве аргумента функции get_api_answer
    current_date = response.get('current_date')
    if 'homeworks' in response:
        homeworks_info = response.get('homeworks')
        if not homeworks_info:
            raise NonCritical('Домашка без изменений!')
        if isinstance(homeworks_info, list):
            return homeworks_info
        else:
            raise CriticalErrors('Неизвестный формат ответа!')
    else:
        raise KeyNotFoundError('Нет homeworks в ключах ответа!')


def parse_status(homework):
    """Извлечение статуса из информации о домашнем задании."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyNotFoundError('Ответ не содержит названия ДЗ!')
    homework_status = homework.get('status')
    if homework_status is None:
        raise KeyNotFoundError('Ответ не содержит статуса ДЗ!')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    if verdict is None:
        raise KeyNotFoundError('Недокументированный статус ответа!')
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
        return sys.exit(
            'Программа закончила свою работу. Нет переменных окружения!'
        )
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    list_errors_occurred = []
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework[0])

        # при отсутствии изменений в ДЗ функция get_api_answer будет вызвана с
        # временной точки, равной ключу current_date
        # API ответа прошлой итерации
        except NonCritical as debug:
            current_timestamp = current_date
            logger.debug(debug)

        # если происходит ошибка CriticalErrors, то на следующей итерации
        # передаем функции get_api_answer в качестве аргумента временную
        # точку, когда в последний раз был получен валидный ответ или
        # точку начала работы программы в случае. если с начала ее работы
        # не приходило валидных ответов.
        except (CriticalErrors, KeyNotFoundError) as error:
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

        # при изменении состояния ДЗ get_api_answer будет вызвана с
        # временной точки, равной ключу current_date
        # API ответа прошлой итерации
        else:
            if current_date:
                current_timestamp = current_date
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    current_date = None
    main()
