import logging
import os
from datetime import datetime

import pytz
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

import settings

tz = pytz.timezone('Europe/Moscow')


def stringify(username: str):
    return username.replace('-', '_')


def slugify(username: str):
    return username.replace('_', '-')


def current_date():
    now = datetime.now(tz)
    date = now.date()
    return date


def compare_date_str_to_now(date_str):
    date_now = current_date()
    date_obj_ = datetime.strptime(date_str, '%Y-%m-%d').date()
    if date_obj_ < date_now:
        return -1
    elif date_obj_ == date_now:
        return 0
    else:
        return 1


def del_from_redis(key):
    try:
        redis = Redis.from_url(url=settings.REDIS_URL)
        redis.delete(key)
    except RedisConnectionError as error:
        logging.error(error)
