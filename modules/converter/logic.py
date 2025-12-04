import pandas as pd
from lxml import etree
from pathlib import Path
from openpyxl.styles import PatternFill
import sys

# Import shared utilities from the parent 'utils' package
from utils.shared import (
    CONFIG, 
    log_errors, 
    get_target_language, 
    compress_ids, 
    decompress_ids, 
    xliff_to_dataframe, 
    update_glossary_file
)

# --- HELPER: Update XLIFF XML from Dictionary Map ---
def update_xliff_from_map(original_path, lang_specific_map):
    """Parses XLIFF and updates targets based on ID match in the map."""
    tree = etree.parse(original_path)
    ns = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
    etree.register_namespace('xliff', ns['xliff'])
    
    for trans_unit in tree.xpath('//xliff:trans-unit', namespaces=ns):
        unit_id = trans_unit.get('id')
        
        if unit_id and unit_id in lang_specific_map:
            target_element = trans_unit.find('xliff:target', namespaces=ns)
            
            if target_element is None:
                target_element = etree.SubElement(trans_unit, f"{{{ns['xliff']}}}target")
            
            target_element.text = lang_specific_map[unit_id]
            target_element.set('state', 'translated')
    return tree

# --- HELPER: Standard File Processing (Repo Replacement) ---
def process_standard_files(root_path, translated_dir):
    """Replaces specific system files with master versions from the repo."""
    repo_name = CONFIG["folder_names"]["master_repo"]
    repo_path = Path(repo_name)
    
    # Try finding repo relative to executable or script
    if not repo_path.exists():
        if getattr(sys, 'frozen', False):
            repo_path = Path(sys.executable).parent / repo_name
        else:
            # Assumes main.py is 2 levels up from here
            repo_path = Path(__file__).parent.parent.parent / repo_name
        
        if not repo_path.exists():
            return 

    prefixes = ["localization-localization_", "localizationerrors-localizationerrors_"]
    course_id = None
    all_translated_files = list(translated_dir.glob('*.xliff'))
    content_files = [f for f in all_translated_files if not f.name.startswith(('localization-', 'localizationerrors-'))]
    
    if content_files:
        try:
            tree = etree.parse(str(content_files[0]))
            file_node = tree.find('.//xliff:file', namespaces={'xliff': 'urn:oasis:names:tc:xliff:document:1.2'})
            if file_node is not None:
                course_id = file_node.get('id')
        except Exception as e:
            raise ValueError(f"Could not determine course ID: {e}")
    
    if not course_id: return

    for prefix in prefixes:
        for standard_file in translated_dir.glob(f"{prefix}*.xliff"):
            lang_code = standard_file.name.replace(prefix, "").replace(".xliff", "")
            master_file_path = repo_path / standard_file.name
            
            if master_file_path.exists():
                try:
                    master_tree = etree.parse(str(master_file_path))
                    file_node = master_tree.find('.//xliff:file', namespaces={'xliff': 'urn:oasis:names:tc:xliff:document:1.2'})
                    if file_node is not None:
                        file_node.set('id', course_id)
                    
                    master_tree.write(str(standard_file), pretty_print=True, xml_declaration=True, encoding='UTF-8')

                    sorted_lang_path = translated_dir / "Separate Languages" / lang_code / standard_file.name
                    if sorted_lang_path.exists():
                        master_tree.write(str(sorted_lang_path), pretty_print=True, xml_declaration=True, encoding='UTF-8')
                except Exception as e:
                    log_errors(root_path, [f"Failed to replace master file {standard_file.name}: {e}"])

# --- FEATURE 1: DeepL Application ---
def apply_deepl_translations(root_path):
    # Note: The GUI asks for the DeepL folder path, so we assume we get it here,
    # BUT since logic shouldn't have popups, we'll assume the GUI passes both paths.
    # However, to match previous signature, we will have to hardcode the "excel export" folder lookup here
    # and assume the GUI handles the "Select DeepL Folder" interaction.
    # ... Wait, the original logic had the popup inside.
    # To follow the architecture strictly, we should pass the deepL path in.
    # For now, let's keep it matching the GUI call: 
    #   GUI: askdirectory -> pass to logic.
    pass 
    # Actually, looking at the GUI code I gave you:
    # `u, t, e = apply_deepl_translations(Path(root))` 
    # The GUI code I provided had the prompt inside `run_apply_deepl` but NOT passed to logic.
    # Let's fix that. The logic should accept the `deepl_folder_path`.
    
    # REVISED SIGNATURE: apply_deepl_translations(root_path, deepl_folder_path)
    # I will stick to the architecture where LOGIC does not do UI.
    raise NotImplementedError("This function requires the DeepL path to be passed from the GUI.")

# Redefining for actual use:
def apply_deepl_translations(root_path, deepl_folder_path=None):
    # If GUI didn't pass it (older call), we can't proceed without UI interaction.
    # We will assume `deepl_folder_path` is passed.
    
    if not deepl_folder_path:
        return 0, 0, ["DeepL folder path was not provided."]

    master_folder_name = CONFIG["folder_names"]["excel_export"]
    master_folder = root_path / master_folder_name
    
    if not master_folder.exists():
        raise ValueError(f"The '{master_folder_name}' folder was not found.")

    deepl_folder = Path(deepl_folder_path)
    master_files = list(master_folder.glob("*-master.xlsx"))
    deepl_files = list(deepl_folder.glob("*.xlsx"))

    if not master_files:
        raise ValueError(f"No master Excel files found in '{master_folder_name}'.")
    if not deepl_files:
        raise ValueError(f"No .xlsx files found in the selected DeepL folder.")

    updated_count = 0
    errors = []

    for master_file in master_files:
        base_lang_code = master_file.name.replace("-master.xlsx", "")
        matching_deepl_file = None

        for df in deepl_files:
            if df.name.lower().startswith(base_lang_code.lower()):
                matching_deepl_file = df
                break
        
        if not matching_deepl_file:
            errors.append(f"No matching DeepL file found for master file: {master_file.name}")
            continue

        try:
            deepl_df = pd.read_excel(matching_deepl_file, header=None, skiprows=1)
            translations = deepl_df.iloc[:, 0].astype(str).fillna('')

            master_wb = pd.ExcelFile(master_file)
            sheet_name = f"{base_lang_code}-Translate_Here"
            
            if sheet_name not in master_wb.sheet_names:
                errors.append(f"Sheet '{sheet_name}' not found in {master_file.name}")
                continue
                
            master_df = pd.read_excel(master_wb, sheet_name=sheet_name)
            
            if len(translations) != len(master_df):
                 errors.append(f"Row count mismatch for {master_file.name}. Master has {len(master_df)} rows, DeepL file has {len(translations)} rows.")
                 continue

            master_df['target'] = translations
            
            with pd.ExcelWriter(master_file, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                master_df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            updated_count += 1

        except Exception as e:
            errors.append(f"Failed to process {master_file.name} with {matching_deepl_file.name}: {e}")

    return updated_count, len(master_files), errors

# --- FEATURE 2: Analysis ---
def perform_analysis(root_path, glossary_path=None):
    xliff_files = list(root_path.glob('*.xliff'))
    if not xliff_files: raise ValueError("No .xliff files were found.")
    
    glossary_map = {}
    if glossary_path and Path(glossary_path).exists():
        glossary_df = pd.read_excel(glossary_path)
        for _, row in glossary_df.iterrows():
            lang = row.get('language_code', 'unknown')
            if lang not in glossary_map: glossary_map[lang] = {}
            glossary_map[lang][row['source_text'].strip()] = row['target_text']
            
    all_records = []
    for file in xliff_files:
        lang = get_target_language(file)
        df = xliff_to_dataframe(file)
        if not df.empty:
            df['language'] = lang
            df['word_count'] = df['source'].str.split().str.len()
            all_records.append(df)
            
    if not all_records: raise ValueError("No translatable content found to analyze.")
    
    master_df = pd.concat(all_records, ignore_index=True)
    master_df['source'] = master_df['source'].str.strip()
    analysis_results = {}
    
    for lang_code, lang_df in master_df.groupby('language'):
        unique_segments = lang_df.drop_duplicates(subset=['source'], keep='first')
        repeated_segments = lang_df[lang_df.duplicated(subset=['source'], keep=False)]
        reps_words = repeated_segments['word_count'].sum() - unique_segments[unique_segments['source'].isin(repeated_segments['source'])]['word_count'].sum()
        
        lang_glossary = glossary_map.get(lang_code, {})
        is_glossary_match = unique_segments['source'].isin(lang_glossary.keys())
        glossary_words = unique_segments[is_glossary_match]['word_count'].sum()
        
        is_new = ~unique_segments['source'].isin(lang_glossary.keys())
        new_words = unique_segments[is_new]['word_count'].sum()
        
        analysis_results[lang_code] = {
            'Total Words': lang_df['word_count'].sum(),
            'Repetitions': reps_words,
            'Glossary Matches': glossary_words,
            'New Words': new_words
        }
    return analysis_results

# --- FEATURE 3: Export to Excel ---
def export_to_excel_with_glossary(root_path, glossary_path=None):
    xliff_files = list(root_path.glob('*.xliff'))
    if not xliff_files: raise ValueError("No .xliff files were found.")
    
    glossary_map = {}
    if glossary_path and Path(glossary_path).exists():
        glossary_df = pd.read_excel(glossary_path)
        for _, row in glossary_df.iterrows():
            lang = row.get('language_code', 'unknown')
            if lang not in glossary_map: glossary_map[lang] = {}
            glossary_map[lang][row['source_text'].strip()] = row['target_text']
            
    output_dir_name = CONFIG["folder_names"]["excel_export"]
    output_dir = root_path / output_dir_name
    output_dir.mkdir(exist_ok=True)
    
    all_records, errors = [], []
    
    for file in xliff_files:
        try:
            lang = get_target_language(file)
            df = xliff_to_dataframe(file)
            if not df.empty:
                df['original_source_file'] = file.name
                df['language'] = lang
                all_records.append(df)
        except Exception as e:
            errors.append(f"Failed to read or process {file.name}: {e}")
            
    if not all_records:
        if errors: log_errors(root_path, errors)
        raise ValueError("No translatable content was found after applying filters.")
        
    master_df = pd.concat(all_records, ignore_index=True)
    master_df['source'] = master_df['source'].str.strip()
    processed_langs = 0
    
    for lang_code, lang_df in master_df.groupby('language'):
        try:
            master_workbook_path = output_dir / f"{lang_code}-master.xlsx"
            with pd.ExcelWriter(master_workbook_path, engine='openpyxl') as writer:
                translate_sheet_name = f"{lang_code}-Translate_Here"
                
                deduplicated = lang_df.groupby('source').agg(
                    existing_target=('existing_target', lambda x: next((s for s in x if s), '')),
                    count=('id', 'size'),
                    locations=('original_source_file', lambda x: ', '.join(x.unique())),
                    id_blob=('id', lambda x: compress_ids(list(x)))
                ).reset_index()

                deduplicated['target'] = deduplicated['existing_target']
                deduplicated['status'] = ''
                deduplicated['add_to_glossary'] = ''
                
                lang_glossary = glossary_map.get(lang_code, {})
                for index, row in deduplicated.iterrows():
                    source_lower = row['source'].lower()

                    if source_lower in CONFIG["protected_set"]:
                        deduplicated.at[index, 'target'] = row['source'] 
                        deduplicated.at[index, 'status'] = 'Protected (Language Name)'
                        continue 

                    if not row['target'] and row['source'] in lang_glossary:
                        deduplicated.at[index, 'target'] = lang_glossary[row['source']]
                        deduplicated.at[index, 'status'] = 'Pre-translated from Glossary'
                    elif row['target']:
                        deduplicated.at[index, 'status'] = 'Existing translation'
                
                deduplicated = deduplicated[['source', 'target', 'count', 'locations', 'status', 'add_to_glossary', 'id_blob']]
                deduplicated.to_excel(writer, sheet_name=translate_sheet_name, index=False)
                
                workbook, worksheet = writer.book, writer.sheets[translate_sheet_name]
                worksheet.column_dimensions['G'].hidden = True
                
                grey_fill = PatternFill(start_color="F0F0F0", end_color="F0F0F0", fill_type="solid")
                for row_idx, status in enumerate(deduplicated['status'], start=2):
                    if status in ('Pre-translated from Glossary', 'Protected (Language Name)'):
                        for col_idx in range(1, len(deduplicated.columns) + 1):
                            worksheet.cell(row=row_idx, column=col_idx).fill = grey_fill
                
                # Context sheets
                for filename, file_df in lang_df.groupby('original_source_file'):
                    sheet_name = Path(filename).stem[:31]
                    if 'existing_target' in file_df.columns:
                        file_df.to_excel(writer, sheet_name=sheet_name, index=False, columns=['id', 'source', 'existing_target', 'gomo-id (context)'])
                    else:
                         file_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    workbook[sheet_name].sheet_state = 'hidden'
                
                workbook.active = worksheet
            processed_langs += 1
        except Exception as e:
            errors.append(f"Could not create master workbook for language '{lang_code}': {e}")
            
    if errors: log_errors(root_path, errors)
    return len(xliff_files), processed_langs, len(errors)

# --- FEATURE 4: Import and Reconstruct ---
def import_and_reconstruct_with_glossary(root_path, glossary_path=None):
    input_dir_name = CONFIG["folder_names"]["excel_export"]
    input_dir = root_path / input_dir_name
    
    if not input_dir.exists(): raise ValueError(f"'{input_dir_name}' folder not found.")
    master_files = list(input_dir.glob('*-master.xlsx'))
    if not master_files: raise ValueError("No '*-master.xlsx' files found.")
    
    errors = []
    
    # 1. Update Glossary
    try:
        new_glossary_entries = []
        for master_file in master_files:
            lang_code = master_file.name.replace("-master.xlsx", "")
            try:
                df = pd.read_excel(master_file, sheet_name=f"{lang_code}-Translate_Here")
                if 'add_to_glossary' in df.columns:
                    df_to_add = df[df['add_to_glossary'].astype(str).str.strip().str.lower().isin(['x', 'yes'])]
                    for _, row in df_to_add.iterrows():
                        if pd.notna(row['target']) and str(row['target']).strip() != '':
                            new_glossary_entries.append({'source_text': row['source'], 'target_text': str(row['target']), 'language_code': lang_code})
            except ValueError:
                errors.append(f"Skipped glossary update for {master_file.name}: 'Translate_Here' sheet not found.")
        if new_glossary_entries and glossary_path:
            update_glossary_file(glossary_path, new_glossary_entries)
    except Exception as e:
        errors.append(f"A critical error occurred while updating the glossary: {e}")

    # 2. Build Translation Map
    translation_map = {}
    
    for master_file in master_files:
        try:
            lang_code = master_file.name.replace("-master.xlsx", "")
            if lang_code not in translation_map: translation_map[lang_code] = {}
            
            sheet_name = f"{lang_code}-Translate_Here"
            df = pd.read_excel(master_file, sheet_name=sheet_name)
            
            if 'target' not in df.columns or 'id_blob' not in df.columns:
                errors.append(f"Missing required columns (target or id_blob) in {master_file.name}.")
                continue

            df.dropna(subset=['target', 'id_blob'], inplace=True)
            
            for _, row in df.iterrows():
                target_text = str(row['target'])
                blob = str(row['id_blob'])
                ids = decompress_ids(blob)
                
                for unit_id in ids:
                    translation_map[lang_code][unit_id] = target_text

        except Exception as e:
            errors.append(f"Could not build translation map from {master_file.name}: {e}")

    # 3. Reconstruct XLIFFs
    xliff_output_name = CONFIG["folder_names"]["xliff_output"]
    translated_dir = root_path / xliff_output_name
    separate_lang_dir = translated_dir / "Separate Languages"
    translated_dir.mkdir(exist_ok=True); separate_lang_dir.mkdir(exist_ok=True)
    processed_count = 0
    original_files = list(root_path.glob('*.xliff'))
    
    for xliff_file in original_files:
        try:
            lang_code_xml = get_target_language(xliff_file)
            
            # Lookup in map
            lang_specific_map = translation_map.get(lang_code_xml, {})
            
            # Fallback check
            if not lang_specific_map:
                for key in translation_map:
                    if key.lower() == lang_code_xml.lower():
                        lang_specific_map = translation_map[key]
                        break

            modified_tree = update_xliff_from_map(xliff_file, lang_specific_map)
            
            primary_path = translated_dir / xliff_file.name
            modified_tree.write(primary_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')
            
            lang_dir = separate_lang_dir / lang_code_xml
            lang_dir.mkdir(exist_ok=True)
            secondary_path = lang_dir / xliff_file.name
            modified_tree.write(secondary_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')
            processed_count += 1
        except Exception as e:
            errors.append(f"Could not reconstruct file {xliff_file.name}: {e}")
            
    try:
        process_standard_files(root_path, translated_dir)
    except Exception as e:
        errors.append(f"An error occurred during standard file processing: {e}")

    if errors: log_errors(root_path, errors)
    return processed_count, len(errors)