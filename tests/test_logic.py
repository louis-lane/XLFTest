import pytest
from utils.core import compress_ids, decompress_ids
from modules.editor.logic import EditorLogic

# --- TEST 1: Check Core Utilities (Compression) ---
def test_id_compression_roundtrip():
    """Test that IDs can be compressed and restored perfectly."""
    original_ids = ["unit_1", "unit_2", "unit_3"]
    
    # Compress
    blob = compress_ids(original_ids)
    assert isinstance(blob, str)
    assert len(blob) > 0
    
    # Decompress
    restored_ids = decompress_ids(blob)
    assert restored_ids == original_ids

def test_empty_compression():
    """Test handling of empty lists."""
    assert compress_ids([]) == ""
    assert decompress_ids("") == []

# --- TEST 2: Check Editor Logic (Tag Extraction) ---
def test_tag_extraction_standard():
    """Test extracting XML tags."""
    logic = EditorLogic()
    text = "Hello <bold>World</bold> with <br/> break."
    
    tags = logic.extract_tags(text, "Standard XML <>")
    
    # We expect '<bold>' and '<br/>'. 
    # Note: The logic might return unique openers. Adjust expectations based on your logic.
    assert "<bold>" in tags
    assert "<br/>" in tags
    # Ensure closing tags are NOT in the list (based on your logic filtering them)
    assert "</bold>" not in tags

def test_tag_extraction_gomo():
    """Test extracting Gomo tags."""
    logic = EditorLogic()
    text = "Hello [b]World[/b] [img src='1.jpg']"
    
    tags = logic.extract_tags(text, "Gomo []")
    
    assert "[b]" in tags
    assert "[img src='1.jpg']" in tags
