import pendulum
import pytest

from infrahub_sdk.timestamp import Timestamp, TimestampFormatError


def test_init_empty():
    t1 = Timestamp()
    assert isinstance(t1, Timestamp)
    assert t1.to_string() == t1.obj.to_iso8601_string()

    t2 = Timestamp(None)
    assert isinstance(t2, Timestamp)
    assert t2.to_string() == t2.obj.to_iso8601_string()


def test_init_timestamp():
    t1 = Timestamp()
    t2 = Timestamp(t1)
    assert t1.to_string() == t2.to_string()
    assert isinstance(t2, Timestamp)
    assert t2.to_string() == t2.obj.to_iso8601_string()


def test_parse_string():
    REF = "2022-01-01T10:00:00.000000Z"

    assert Timestamp._parse_string(REF) == pendulum.parse(REF)
    assert Timestamp._parse_string("5m")
    assert Timestamp._parse_string("10min")
    assert Timestamp._parse_string("2h")
    assert Timestamp._parse_string("10s")

    with pytest.raises(ValueError):
        Timestamp._parse_string("notvalid")


def test_compare():
    time1 = "2022-01-01T11:00:00.000000Z"
    time2 = "2022-02-01T11:00:00.000000Z"

    t11 = Timestamp(time1)
    t12 = Timestamp(time1)

    t21 = Timestamp(time2)

    assert t11 < t21
    assert t21 > t12
    assert t11 <= t12
    assert t11 >= t12
    assert t11 == t12


@pytest.mark.parametrize("invalid_str", ["blurple", "1122334455667788", "2023-45-99"])
def test_invalid_raises_correct_error(invalid_str):
    with pytest.raises(TimestampFormatError):
        Timestamp(invalid_str)
