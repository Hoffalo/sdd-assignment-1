import pytest

from tests.doubles import FixedClock, SequentialTokens


@pytest.fixture
def clock():
    return FixedClock()


@pytest.fixture
def tokens():
    return SequentialTokens()
