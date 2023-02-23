"""Testing of RedisStore."""
import pytest
from diffsync.store.redis import RedisStore
from diffsync.exceptions import ObjectStoreException


def _get_path_from_redisdb(redisdb_instance):
    return f"unix://{redisdb_instance.connection_pool.connection_kwargs['path']}"


def test_redisstore_init(redisdb):
    store = RedisStore(name="mystore", store_id="123", url=_get_path_from_redisdb(redisdb))
    assert str(store) == "mystore (123)"


def test_redisstore_init_wrong():
    with pytest.raises(ObjectStoreException):
        RedisStore(name="mystore", store_id="123", url="redis://wrong")


def test_redisstore_add_obj(redisdb, make_site):
    store = RedisStore(name="mystore", store_id="123", url=_get_path_from_redisdb(redisdb))
    site = make_site()
    store.add(obj=site)
    assert store.count() == 1


def test_redisstore_add_obj_twice(redisdb, make_site):
    store = RedisStore(name="mystore", store_id="123", url=_get_path_from_redisdb(redisdb))
    site = make_site()
    store.add(obj=site)
    store.add(obj=site)
    assert store.count() == 1


def test_redisstore_get_all_obj(redisdb, make_site):
    store = RedisStore(name="mystore", store_id="123", url=_get_path_from_redisdb(redisdb))
    site = make_site()
    store.add(obj=site)
    assert store.get_all(model=site.__class__)[0] == site


def test_redisstore_get_obj(redisdb, make_site):
    store = RedisStore(name="mystore", store_id="123", url=_get_path_from_redisdb(redisdb))
    site = make_site()
    store.add(obj=site)
    assert store.get(model=site.__class__, identifier=site.name) == site


def test_redisstore_remove_obj(redisdb, make_site):
    store = RedisStore(name="mystore", store_id="123", url=_get_path_from_redisdb(redisdb))
    site = make_site()
    store.add(obj=site)
    assert store.count(model=site.__class__) == store.count() == 1
    store.remove(obj=site)
    assert store.count(model=site.__class__) == store.count() == 0


def test_redisstore_get_all_model_names(redisdb, make_site, make_device):
    store = RedisStore(name="mystore", store_id="123", url=_get_path_from_redisdb(redisdb))
    site = make_site()
    store.add(obj=site)
    device = make_device()
    store.add(obj=device)
    assert site.get_type() in store.get_all_model_names()
    assert device.get_type() in store.get_all_model_names()
