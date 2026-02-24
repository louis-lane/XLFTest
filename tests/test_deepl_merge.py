import pytest
import pandas as pd
from pathlib import Path
from modules.converter.deepl import apply_deepl_translations
from utils.core import CONFIG

def test_shuffled_row_merge(tmp_path, monkeypatch):
    """
    Simulates a scenario where DeepL returns translations in a completely 
    different row order than the Master file.
    """
    # 1. Setup Mock Directories
    export_dir = "1_Excel_for_Translation"
    master_folder = tmp_path / export_dir
    master_folder.mkdir()
    
    deepl_folder = tmp_path / "DeepL_Output"
    deepl_folder.mkdir()

    # Monkeypatch the config so the function looks in our tmp_path
    monkeypatch.setitem(CONFIG["folder_names"], "excel_export", export_dir)

    # 2. Create a Fake Master File
    master_file = master_folder / "fr-master.xlsx"
    master_df = pd.DataFrame({
        "source": ["Apple", "Banana", "Cherry"],
        "target": ["", "", ""],
        "status": ["", "", ""],
        "fingerprint": ["hashA", "hashB", "hashC"]
    })
    
    with pd.ExcelWriter(master_file, engine='openpyxl') as writer:
        master_df.to_excel(writer, sheet_name="fr-Translate_Here", index=False)

    # 3. Create a Fake DeepL Output File (Notice the order is 3, 1, 2)
    deepl_file = deepl_folder / "fr_MT_Output.xlsx"
    deepl_df = pd.DataFrame({
        "target": ["Cerise", "Pomme", "Banane"], # Translated text
        "fingerprint": ["hashC", "hashA", "hashB"] # Matching fingerprints
    })
    deepl_df.to_excel(deepl_file, index=False)

    # 4. Run the Tool
    updated, total, errors = apply_deepl_translations(tmp_path, str(deepl_folder))

    # 5. Verify the Results
    assert updated == 1
    assert len(errors) == 0

    # Read the updated master file to ensure text went to the right place
    updated_master = pd.read_excel(master_file, sheet_name="fr-Translate_Here")
    
    # Apple (hashA) should now be "Pomme"
    assert updated_master.loc[updated_master['fingerprint'] == 'hashA', 'target'].values[0] == "Pomme"
    # Cherry (hashC) should now be "Cerise"
    assert updated_master.loc[updated_master['fingerprint'] == 'hashC', 'target'].values[0] == "Cerise"
