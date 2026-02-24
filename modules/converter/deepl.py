import pandas as pd
from pathlib import Path
from typing import Tuple, List, Optional
from utils.core import CONFIG

def apply_deepl_translations(root_path: Path, deepl_folder_path: Optional[str]) -> Tuple[int, int, List[str]]:
    master_folder = root_path / str(CONFIG["folder_names"]["excel_export"])
    if not master_folder.exists():
        raise ValueError("Master folder not found.")

    if not deepl_folder_path:
        return 0, 0, ["User cancelled."]

    deepl_folder = Path(deepl_folder_path)
    master_files = list(master_folder.glob("*-master.xlsx"))
    deepl_files = list(deepl_folder.glob("*.xlsx"))

    if not master_files:
        raise ValueError("No master files found.")
    if not deepl_files:
        raise ValueError("No DeepL files found.")

    updated_count = 0
    errors: List[str] = []

    for master_file in master_files:
        base_lang_code = master_file.name.replace("-master.xlsx", "")
        matching_deepl = next((df for df in deepl_files if df.name.lower().startswith(base_lang_code.lower())), None)
        
        if not matching_deepl:
            errors.append(f"No match for: {master_file.name}")
            continue

        try:
            # Load the translated DeepL file
            deepl_df = pd.read_excel(matching_deepl)
            
            if len(deepl_df.columns) < 2:
                errors.append(f"DeepL file {matching_deepl.name} missing fingerprint column.")
                continue
            
            # Phase 3 mapping logic: Dictionary matching
            trans_map = dict(zip(deepl_df.iloc[:, 1].astype(str).str.strip(), deepl_df.iloc[:, 0].astype(str).fillna('')))

            sheet_name = f"{base_lang_code}-Translate_Here"
            
            # THE FIX: Let read_excel safely open/close the file for us
            try:
                master_df = pd.read_excel(master_file, sheet_name=sheet_name)
            except ValueError:
                errors.append(f"Sheet '{sheet_name}' missing in {master_file.name}")
                continue
            
            if 'fingerprint' not in master_df.columns:
                errors.append(f"Fingerprint column missing in master {master_file.name}. Cannot merge.")
                continue

            unmatched = 0
            for idx, row in master_df.iterrows():
                if row.get('status') in ['Protected', 'Glossary']:
                    continue

                fp = str(row.get('fingerprint', '')).strip()
                if fp in trans_map:
                    master_df.at[idx, 'target'] = trans_map[fp]
                else:
                    unmatched += 1
            
            if unmatched > 0:
                errors.append(f"{unmatched} unmatched segments in {master_file.name}")

            # Safe to write now, the file isn't locked!
            with pd.ExcelWriter(master_file, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                master_df.to_excel(writer, sheet_name=sheet_name, index=False)
                ws = writer.sheets[sheet_name]
                ws.column_dimensions['G'].hidden = True
                ws.column_dimensions['H'].hidden = True
            
            updated_count += 1
        except Exception as e:
            errors.append(f"Error {master_file.name}: {e}")

    return updated_count, len(master_files), errors
