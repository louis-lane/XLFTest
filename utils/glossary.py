import pandas as pd
from pathlib import Path
from utils.shared import get_target_language

def load_glossary_dataframe(glossary_path):
    """Safely loads the glossary Excel file into a DataFrame."""
    if not glossary_path or not Path(glossary_path).exists():
        return pd.DataFrame()
    try:
        return pd.read_excel(glossary_path).fillna("")
    except Exception as e:
        print(f"Glossary Load Error: {e}")
        return pd.DataFrame()

def get_glossary_map(glossary_path):
    """
    Returns a simple dictionary {lang_code: {source: target}} for bulk translation.
    Used by the Converter module.
    """
    glossary_map = {}
    df = load_glossary_dataframe(glossary_path)
    if df.empty: return glossary_map

    for _, row in df.iterrows():
        # Respect forbidden flag if it exists
        if str(row.get('is_forbidden', 'FALSE')).strip().upper() == 'TRUE':
            continue
            
        lang = str(row.get('language_code', 'unknown')).strip()
        if lang not in glossary_map: glossary_map[lang] = {}
        
        # Simple Key-Value mapping
        source = str(row.get('source_text', '')).strip()
        target = str(row.get('target_text', '')).strip()
        if source and target:
            glossary_map[lang][source] = target
            
    return glossary_map

def find_glossary_matches(source_text, current_file_path, glossary_data):
    """
    Complex matching logic for the Editor (Exact, Partial, Case Sensitive).
    glossary_data should be a list of dicts (loaded via load_glossary_as_dict).
    """
    matches = []
    if not glossary_data or not source_text: return matches

    current_lang = "unknown"
    if current_file_path: current_lang = get_target_language(current_file_path)
    source_lower = source_text.lower()

    for entry in glossary_data:
        if entry['is_forbidden']: continue
        if entry['lang'] and current_lang != "unknown":
            if not current_lang.lower().startswith(entry['lang'].lower()): continue

        term = entry['source']
        is_match = False
        
        # Match Logic
        if entry['match_type'] == 'exact':
            if entry['case_sensitive']: is_match = (term == source_text)
            else: is_match = (term.lower() == source_lower)
        else: # Partial
            if entry['case_sensitive']: is_match = (term in source_text)
            else: is_match = (term.lower() in source_lower)

        if is_match: matches.append((term, entry['target']))
    
    return matches

def load_glossary_as_list(glossary_path):
    """Loads glossary as a list of dictionaries for the Editor."""
    data = []
    df = load_glossary_dataframe(glossary_path)
    if df.empty: return data

    for _, row in df.iterrows():
        s = str(row.get('source_text', '')).strip()
        t = str(row.get('target_text', '')).strip()
        if s and t:
            data.append({
                "source": s,
                "target": t,
                "lang": str(row.get('language_code', '')).strip(),
                "match_type": str(row.get('match_type', 'partial')).strip(),
                "case_sensitive": str(row.get('case_sensitive', 'FALSE')).strip().upper() == 'TRUE',
                "context": str(row.get('context', '')).strip(),
                "is_forbidden": str(row.get('is_forbidden', 'FALSE')).strip().upper() == 'TRUE'
            })
    return data

def add_term_to_file(glossary_path, term_data):
    """Appends a single term to the Excel file."""
    path = Path(glossary_path)
    new_df = pd.DataFrame([term_data])
    
    if path.exists():
        existing_df = pd.read_excel(path).fillna("")
        combined = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined = new_df
        
    combined.to_excel(path, index=False)

def update_glossary_from_list(glossary_path, new_entries):
    """Bulk update used by the Converter (replaces update_glossary_file)."""
    if not new_entries: return
    
    path = Path(glossary_path)
    if path.exists():
        glossary_df = pd.read_excel(path)
    else:
        glossary_df = pd.DataFrame(columns=['source_text', 'target_text', 'language_code'])
        
    new_entries_df = pd.DataFrame(new_entries)
    combined_df = pd.concat([glossary_df, new_entries_df], ignore_index=True)
    
    # Deduplicate based on Source and Language
    combined_df.drop_duplicates(subset=['source_text', 'language_code'], keep='first', inplace=True)
    combined_df.to_excel(path, index=False)
