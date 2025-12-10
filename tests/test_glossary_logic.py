import pytest
from utils.glossary import find_glossary_matches

# Fixture: A sample glossary loaded as a list of dicts (simulating load_glossary_as_list)
@pytest.fixture
def sample_glossary():
    return [
        {
            "source": "Hello", "target": "Bonjour", 
            "lang": "fr", "match_type": "exact", 
            "case_sensitive": True, "is_forbidden": False
        },
        {
            "source": "world", "target": "monde", 
            "lang": "fr", "match_type": "partial", 
            "case_sensitive": False, "is_forbidden": False
        },
        {
            "source": "forbidden_term", "target": "", 
            "lang": "", "match_type": "partial", 
            "case_sensitive": False, "is_forbidden": True
        }
    ]

def test_exact_match_success(sample_glossary):
    # Should match "Hello" exactly
    matches = find_glossary_matches("Hello", None, sample_glossary)
    assert len(matches) == 1
    assert matches[0][0] == "Hello"
    assert matches[0][1] == "Bonjour"

def test_exact_match_case_failure(sample_glossary):
    # Should NOT match "hello" (lowercase) because case_sensitive is True
    matches = find_glossary_matches("hello", None, sample_glossary)
    assert len(matches) == 0

def test_partial_match_success(sample_glossary):
    # Should match "world" inside a sentence (partial + case insensitive)
    matches = find_glossary_matches("Hello big world", None, sample_glossary)
    assert len(matches) == 1
    assert matches[0][0] == "world"

def test_forbidden_term(sample_glossary):
    # Should NOT return forbidden terms even if they match
    matches = find_glossary_matches("This contains a forbidden_term here", None, sample_glossary)
    assert len(matches) == 0
