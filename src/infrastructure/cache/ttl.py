import random

from src.configs.consts import (
    DEFAULT_JITTER_TTL_LOWER_LIMIT,
    DEFAULT_JITTER_TTL_UPPER_LIMIT,
)


def get_int_jitter(
    lower_limit: int = DEFAULT_JITTER_TTL_LOWER_LIMIT,
    upper_limit: int = DEFAULT_JITTER_TTL_UPPER_LIMIT,
) -> int:
    """Добавляет рандомное целое число к TTL"""

    if lower_limit > upper_limit:
        raise ValueError(f"lower_limit ({lower_limit}) не может быть больше upper_limit ({upper_limit})")

    return random.randint(lower_limit, upper_limit)
