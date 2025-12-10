import json
import sys
import copy
from pathlib import Path
from collections import UserDict
from typing import Dict, Any, Optional

class ConfigManager(UserDict):
    """
    Robust configuration handler.
    Acts like a dictionary but handles loading, defaults, and derived values.
    """
    
    # Static Default Configuration (Fallback)
    DEFAULT: Dict[str, Any] = {
        "folder_names": {
            "excel_export": "1_Excel_for_Translation",
            "xliff_output": "2_Translated_XLIFFs",
            "master_repo": "master_localization_files"
        },
        "protected_languages": [
            "English", "British English", "American English", "Español", "Spanish",
            "Français", "French", "Italiano", "Italian", "Deutsch", "German",
            "Português", "Portuguese", "Português (Brasil)", "Svenska", "Swedish",
            "Nederlands", "Dutch", "Dansk", "Danish", "Norsk", "Norwegian",
            "Suomi", "Finnish", "Русский", "Russian", "Українська", "Ukrainian",
            "Polskie", "Polish", "Čeština", "Czech", "Türk", "Turkish",
            "Ελληνικά", "Greek", "Magyar", "Hungarian", "Română", "Romanian",
            "日本語", "Japanese", "한국어", "Korean", "简体中文", "Chinese (Simplified)",
            "繁體中文", "Chinese (Traditional)", "العربية", "Arabic", "עברית", "Hebrew",
            "Bahasa Indonesia", "Indonesian", "Bahasa Melayu", "Malay", "Tiếng Việt", "Vietnamese",
            "ไทย", "Thai", "हिंदी", "Hindi"
        ]
    }

    def __init__(self) -> None:
        # Initialize with a deep copy of defaults so we don't mutate the class attribute
        super().__init__(copy.deepcopy(self.DEFAULT))
        self.config_path: Optional[Path] = None
        self.load_from_file()
        self._generate_derived_data()

    def resolve_root_path(self) -> Path:
        """
        Intelligently finds the project root directory.
        Handles both frozen (PyInstaller) and script environments.
        """
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        
        # Standard dev structure: /utils/config_manager.py -> /utils/ -> /
        current_file = Path(__file__)
        return current_file.parent.parent

    def load_from_file(self) -> None:
        """
        Attempts to load 'config.json' from the root directory.
        Falls back to defaults if the file is missing or invalid.
        """
        root = self.resolve_root_path()
        self.config_path = root / "config.json"
        
        if not self.config_path.exists():
            # If explicit config missing, try looking up one level (robustness for tests)
            if (root.parent / "config.json").exists():
                self.config_path = root.parent / "config.json"
            else:
                return # Keep defaults

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
                self._recursive_update(self.data, user_data)
        except Exception as e:
            print(f"Warning: Failed to load config.json (using defaults): {e}")

    def _recursive_update(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        """
        Recursively merges dictionaries (e.g. folder_names) instead of overwriting.
        """
        for k, v in update.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._recursive_update(base[k], v)
            else:
                base[k] = v

    def _generate_derived_data(self) -> None:
        """Creates fast-lookup sets from the raw lists."""
        langs = self.data.get("protected_languages", [])
        # 'protected_set' is used by the converter for O(1) lookups
        self.data["protected_set"] = {str(x).lower() for x in langs}
