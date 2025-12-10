import pandas as pd
from pathlib import Path
from utils.core import CONFIG

def apply_deepl_translations(root_path, deepl_folder_path):
    master_folder = root_path / CONFIG["folder_names"]["excel_export"]
    if not master_folder.exists(): raise ValueError("Master folder not found.")

    if not deepl_folder_path: return 0, 0, ["User cancelled."]

    deepl_folder = Path(deepl_folder_path)
    master_files = list(master_folder.glob("*-master.xlsx"))
    deepl_files = list(deepl_folder.glob("*.xlsx"))

    if not master_files: raise ValueError("No master files found.")
    if not deepl_files: raise ValueError("No DeepL files found.")

    updated_count = 0
    errors = []

    for master_file in master_files:
        base_lang_code = master_file.name.replace("-master.xlsx", "")
        matching_deepl = next((df for df in deepl_files if df.name.lower().startswith(base_lang_code.lower())), None)
        
        if not matching_deepl:
            errors.append(f"No match for: {master_file.name}")
            continue

        try:
            deepl_df = pd.read_excel(matching_deepl, header=None, skiprows=1)
            translations = deepl_df.iloc[:, 0].astype(str).fillna('')
            master_wb = pd.ExcelFile(master_file)
            sheet_name = f"{base_lang_code}-Translate_Here"
            
            if sheet_name not in master_wb.sheet_names:
                errors.append(f"Sheet '{sheet_name}' missing in {master_file.name}")
                continue
                
            master_df = pd.read_excel(master_wb, sheet_name=sheet_name)
            if len(translations) != len(master_df):
                 errors.append(f"Row mismatch in {master_file.name}")
                 continue
                 
            master_df['target'] = translations
            with pd.ExcelWriter(master_file, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                master_df.to_excel(writer, sheet_name=sheet_name, index=False)
            updated_count += 1
        except Exception as e:
            errors.append(f"Error {master_file.name}: {e}")

    return updated_count, len(master_files), errors
