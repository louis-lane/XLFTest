import pytest
import pandas as pd
from utils.core import get_target_language, xliff_to_dataframe

# Helper to create a dummy XLIFF file
def create_dummy_xliff(path, target_lang="fr-FR"):
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
        <file source-language="en-US" target-language="{target_lang}" datatype="plaintext">
            <body>
                <trans-unit id="1">
                    <source>Hello World</source>
                    <target>Bonjour le monde</target>
                </trans-unit>
                <trans-unit id="2">
                    <source>Untranslated</source>
                    <target></target>
                </trans-unit>
                <trans-unit id="3" translate="no">
                    <source>Do Not Translate</source>
                </trans-unit>
            </body>
        </file>
    </xliff>
    """
    path.write_text(content, encoding="utf-8")
    return path

def test_get_target_language(tmp_path):
    # Create a temporary file
    f = tmp_path / "test.xliff"
    create_dummy_xliff(f, "es-ES")
    
    # Run logic
    lang = get_target_language(f)
    assert lang == "es-ES"

def test_get_target_language_missing(tmp_path):
    # Test fallback for malformed file
    f = tmp_path / "bad.xliff"
    f.write_text("<xml>No xliff here</xml>", encoding="utf-8")
    
    lang = get_target_language(f)
    assert lang == "unknown"

def test_xliff_to_dataframe(tmp_path):
    f = tmp_path / "data.xliff"
    create_dummy_xliff(f, "fr-FR")
    
    df = xliff_to_dataframe(f)
    
    # Checks
    assert not df.empty
    assert len(df) == 2  # Should be 2 (Unit 1 and 2). Unit 3 is translate="no" so it should be skipped.
    assert "Hello World" in df['source'].values
    assert "Untranslated" in df['source'].values
    assert "Do Not Translate" not in df['source'].values
