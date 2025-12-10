import pytest
import json
from utils.config_manager import ConfigManager

def test_defaults_loaded():
    """Ensure that defaults are present even without a file."""
    cfg = ConfigManager()
    assert "folder_names" in cfg
    assert cfg["folder_names"]["excel_export"] == "1_Excel_for_Translation"
    assert "protected_set" in cfg
    # Check that the set was generated correctly
    assert "english" in cfg["protected_set"]

def test_recursive_merge(tmp_path):
    """Ensure user config merges with defaults, not overwrites them."""
    # Create a fake config file
    config_file = tmp_path / "config.json"
    fake_data = {
        "folder_names": {
            "excel_export": "CUSTOM_FOLDER" 
            # Note: other keys like 'xliff_output' are missing here
        }
    }
    config_file.write_text(json.dumps(fake_data), encoding="utf-8")
    
    # Mock the root path resolution to point to tmp_path
    # Since we can't easily mock methods in this simple setup, we can manually load
    cfg = ConfigManager()
    cfg.config_path = config_file
    with open(config_file, 'r', encoding='utf-8') as f:
         cfg._recursive_update(cfg.data, json.load(f))
    
    # Check if the custom value applied
    assert cfg["folder_names"]["excel_export"] == "CUSTOM_FOLDER"
    # Check if the default value persisted (was NOT overwritten)
    assert cfg["folder_names"]["xliff_output"] == "2_Translated_XLIFFs"

def test_protected_set_generation():
    """Test that the case-insensitive set is built."""
    cfg = ConfigManager()
    # Modify the list manually to test generation
    cfg["protected_languages"] = ["TestLang"]
    cfg._generate_derived_data()
    
    assert "testlang" in cfg["protected_set"]
    assert "TestLang" not in cfg["protected_set"]
