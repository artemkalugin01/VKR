import uuid
from datetime import datetime

import redis
import logging
import json

from django.db.models import QuerySet
from django.http import QueryDict

logger = logging.getLogger(__name__)


class CacheDB:
    pools: dict = dict()
    cache: redis.Redis = None

    def __init__(self, host='127.0.0.1', port=6379, db=0):
        key = f'{host}:{port}:{db}'
        if key not in CacheDB.pools:
            CacheDB.pools[key] = CacheDB.get_pool(host, port, db)
        self.cache = CacheDB.pools.get(key)

    @classmethod
    def get_pool(cls, host, port, db):
        logger.info(f'init redis connect: {dict(host=host, port=port, db=db)}')
        return redis.Redis(host=host, port=port, db=db)

    @staticmethod
    def __dec(s):
        return s.decode('utf-8')

    @property
    def is_alive(self):
        try:
            return self.cache.ping()
        except redis.exceptions.ConnectionError:
            return False

    def get(self, key):
        try:
            data = self.cache.get(key)
        except redis.exceptions.ConnectionError:
            return False

        if data:
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = data.decode('utf-8')

        return data

    def last_save(self):
        try:
            return self.cache.lastsave()
        except redis.exceptions.ConnectionError:
            return False

    def keys(self, pattern='*'):
        try:
            return self.cache.keys(pattern=pattern)
        except redis.exceptions.ConnectionError:
            return False

    def search(self, prefix):
        data = list()

        try:
            for key in self.cache.scan_iter(prefix):
                data.append({self.__dec(key): self.get(key)})
        except redis.exceptions.ConnectionError:
            return False

        return data

    def set(self, key, data, ex=None):
        try:
            data = json.dumps(data)
        except TypeError:
            data = data

        try:
            return self.cache.set(key, data, ex=ex)
        except redis.exceptions.ConnectionError as e:
            logger.warning(f'[{self.__class__.__name__}] {e}')
            return False

    def set_many(self, **kwargs):
        """
        kwargs: {'key1': {'key': 'value'}, 'key2': {'key': 'value'}}
        """
        data = {
            key: serialize(value) if is_jsonable(value) else str(value)
            for key, value in kwargs.items()
        }

        if data:
            try:
                self.cache.mset(data)
            except (redis.exceptions.ConnectionError,
                    redis.exceptions.ResponseError) as e:
                logger.warning(f'[{self.__class__.__name__}] {e}')
                return

    def exists(self, key):
        try:
            return self.cache.exists(key)
        except redis.exceptions.ConnectionError:
            return False

    def save(self):
        try:
            return self.cache.save()
        except redis.exceptions.ConnectionError:
            return False

    def delete(self, key):
        try:
            return self.cache.delete(key)
        except redis.exceptions.ConnectionError:
            return False

    def clear(self):
        try:
            return self.cache.flushdb()
        except redis.exceptions.ConnectionError:
            return False

    @property
    def ping(self):
        try:
            return self.cache.ping()
        except redis.exceptions.ConnectionError:
            return False

    @property
    def size(self):
        try:
            return self.cache.dbsize()
        except redis.exceptions.ConnectionError:
            return False

    @property
    def info(self):
        try:
            return self.cache.info()
        except redis.exceptions.ConnectionError:
            return False

    def ttl(self, key):
        try:
            return self.cache.ttl(key)
        except redis.exceptions.ConnectionError:
            return -2


def is_jsonable(obj):
    if not isinstance(obj, (list, dict)):
        return False
    try:
        json.dumps(obj)
        return True
    except (TypeError, OverflowError):
        return False


def serialize(data, indent=None, ensure_ascii=True):
    return json.dumps(data,
                      indent=indent,
                      ensure_ascii=ensure_ascii,
                      default=serializer)


def serializer(o):
    if isinstance(o, QueryDict):
        return dict(o)
    elif isinstance(o, QuerySet):
        return list(o)
    elif isinstance(o, uuid.UUID):
        return str(o)
    elif isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    else:
        return str(o)
