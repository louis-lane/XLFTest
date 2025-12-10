# Localization Toolkit

A modular Python application for managing XLIFF translation workflows. It provides tools to convert XLIFF files to Excel for translation (and back) and a visual editor for direct XLIFF modification.

## 📂 Project Structure

The project is organized into a modular architecture to separate Logic, GUI, and Utilities.

```text
XLFTest/
├── main.py                  # Entry point (Launches the Application)
├── config.json              # User configuration (Protected terms, folders)
├── requirements.txt         # Python dependencies
├── README.md                # Project documentation
│
├── modules/                 # Feature-specific packages
│   ├── converter/           # Excel <-> XLIFF Conversion Tools
│   │   ├── gui.py           # The "Converter" tab interface
│   │   ├── analysis.py      # Logic: Word counts and glossary matching
│   │   ├── export.py        # Logic: Creating Excel master files
│   │   ├── reconstruction.py# Logic: Updating XLIFFs from Excel
│   │   └── deepl.py         # Logic: Merging DeepL raw translations
│   │
│   └── editor/              # Visual XLIFF Editor
│       ├── gui.py           # The "Editor" tab interface
│       ├── logic.py         # Logic: XML parsing and tag handling
│       └── popups.py        # Dialogs (Find/Replace, Add Term)
│
├── utils/                   # Shared Resources
│   ├── core.py              # Pure Logic (File IO, XML, Config loading)
│   ├── gui_utils.py         # GUI Helpers (Window centering)
│   ├── glossary.py          # Centralized Glossary IO & Matching logic
│   └── config_manager.py    # Robust Configuration Handler
│
└── tests/                   # Automated Unit Tests
    ├── test_logic.py        # Tests for core utilities
    ├── test_glossary.py     # Tests for matching rules
    └── ...
