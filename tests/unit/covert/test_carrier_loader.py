import pytest

from covert.carriers import load
from covert.carriers.base import Carrier


def test_abc_cannot_instantiate():
    with pytest.raises(TypeError):
        Carrier()


def test_load_unknown_returns_none():
    assert load("nope-not-a-carrier") is None
