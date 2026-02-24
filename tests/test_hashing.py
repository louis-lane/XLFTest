import pytest
from utils.core import generate_fingerprint

def test_identical_strings_produce_same_hash():
    """Ensure identical strings get the same fingerprint."""
    str1 = "Login to your account"
    str2 = "Login to your account"
    assert generate_fingerprint(str1) == generate_fingerprint(str2)

def test_whitespace_insensitivity():
    """Ensure leading/trailing whitespace doesn't break the match."""
    clean = "Submit"
    messy = "  Submit \n "
    assert generate_fingerprint(clean) == generate_fingerprint(messy)

def test_empty_string_handling():
    """Ensure empty or None values return an empty string safely."""
    assert generate_fingerprint("") == ""
    assert generate_fingerprint(None) == ""

def test_different_strings_produce_unique_hashes():
    """Ensure different strings do not collide."""
    assert generate_fingerprint("Yes") != generate_fingerprint("No")
