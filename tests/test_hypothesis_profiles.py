"""The two hypothesis profiles from tests/conftest.py exist and `full` meets the ROADMAP seed count."""

from hypothesis import settings


def test_full_profile_meets_roadmap_seed_count():
    assert settings.get_profile("full").max_examples >= 200


def test_dev_profile_is_smaller():
    assert settings.get_profile("dev").max_examples < settings.get_profile("full").max_examples


def test_property_tests_have_no_deadline():
    # Engine runs of 300 ticks take far longer than hypothesis' default 200 ms deadline.
    assert settings.get_profile("dev").deadline is None and settings.get_profile("full").deadline is None
