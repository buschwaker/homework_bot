class NonCritical(Exception):
    """Исключение обрабатывающее некритические ошибки"""
    pass


class CriticalErrors(Exception):
    """Исключение обрабатывающее критические ошибки"""
    pass


class KeyNotFoundError(KeyError):
    """Исключение обрабатывающее ошибки связанные с отсутствием ключа"""
    pass
