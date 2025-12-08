import json
import sys
from pathlib import Path
from datetime import datetime
from lxml import etree
import pandas as pd
import zlib
import base64
import re

# --- CONFIGURATION ---
DEFAULT_CONFIG = {
    "folder_names": {
        "excel_export": "1_Excel_for_Translation",
        "xliff_output": "2_Translated_XLIFFs",
        "master_repo": "master_localization_files"
    },
    "protected_languages": [
        "English", "British English", "American English",
        "Español", "Spanish",
        "Français", "French",
        "Italiano", "Italian",
        "Deutsch", "German",
        "Português", "Portuguese", "Português (Brasil)",
        "Svenska", "Swedish",
        "Nederlands-Vlaamse", "Nederlands", "Dutch", "Vlaams",
        "Dansk", "Danish",
        "Norsk", "Norwegian",
        "Suomi", "Finnish",
        "Íslenska", "Icelandic",
        "Gaeilge", "Irish",
        "Cymraeg", "Welsh",
        "Polskie", "Polski", "Polish",
        "Čeština", "Czech",
        "Lietuvių", "Lithuanian",
        "Eesti", "Estonian",
        "Slovenčina", "Slovak",
        "Slovenščina", "Slovenian",
        "Magyar", "Hungarian",
        "Română", "Romanian",
        "Latviešu", "Latvian",
        "Hrvatski", "Croatian",
        "Srpski", "Serbian",
        "Bosanski", "Bosnian",
        "Русский", "Russian",
        "Українська", "Ukrainian",
        "Български", "Bulgarian",
        "Ελληνικά", "Greek",
        "Türk", "Türkçe", "Turkish",
        "Bahasa Indonesia", "Indonesian",
        "Bahasa Melayu", "Malay",
        "Tiếng Việt", "Vietnamese",
        "Tagalog", "Filipino",
        "ไทย", "Thai",
        "简体中文 (中国)", "简体中文", "Chinese (Simplified)",
        "繁體中文 (香港)", "繁體中文", "Chinese (Traditional)", "中國傳統 (香港)",
        "日本語", "Japanese",
        "한국어", "Korean",
        "العربية", "Arabic",
        "עברית", "Hebrew",
        "فارسی", "Persian",
        "اردو", "Urdu",
        "සිංහල", "Sinhala",
        "नेपाली", "Nepali",
        "বাংলা", "Bengali",
        "ગુજરાતી", "Gujarati",
        "हिंदी", "Hindi", "हिन्दी",
        "ಕನ್ನಡ", "Kannada",
        "മലയാളം", "Malayalam",
        "मराठी", "Marathi",
        "ଓଡ଼ିଆ", "Odia",
        "தமிழ்", "Tamil",
        "తెలుగు", "Telugu"
    ]
}

def load_config():
    if getattr(sys, 'frozen', False):
        app_path = Path(sys.executable).parent
    else:
        # Assumes this file is in utils/, so app root is one level up
        app_path = Path(__file__).parent.parent
        
    config_path = app_path / "config.json"
    current = DEFAULT_CONFIG.copy()
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user = json.load(f)
                if "folder_names" in user: current["folder_names"].update(user["folder_names"])
                if "protected_languages" in user: current["protected_languages"] = user["protected_languages"]
        except: pass
        
    current["protected_set"] = {x.lower() for x in current["protected_languages"]}
    return current

CONFIG = load_config()

# --- SHARED HELPERS ---

def log_errors(root_path, errors):
    log_path = Path(root_path) / "error_log.txt"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"\n--- Log Entry: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        for error in errors: f.write(f"- {error}\n")

def get_target_language(xliff_path):
    try:
        tree = etree.parse(xliff_path)
        ns = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
        file_node = tree.find('.//xliff:file', namespaces=ns)
        return file_node.get('target-language', 'unknown') if file_node is not None else 'unknown'
    except: return 'unknown'

def compress_ids(id_list):
    if not id_list: return ""
    try:
        s = "|".join(str(x) for x in id_list)
        return base64.b64encode(zlib.compress(s.encode('utf-8'))).decode('utf-8')
    except: return ""

def decompress_ids(blob):
    if not blob or pd.isna(blob) or str(blob).strip() == "": return []
    try:
        return zlib.decompress(base64.b64decode(str(blob))).decode('utf-8').split('|')
    except: return []

def xliff_to_dataframe(xliff_path):
    ns = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
    tree = etree.parse(xliff_path)
    records = []
    non_translatable = {'left-alignc', 'imagestatic-1', 'video2-1'}
    non_translatable_patterns = [re.compile(r'text-\d+', re.IGNORECASE)]

    for tu in tree.xpath('//xliff:trans-unit', namespaces=ns):
        if tu.get('translate') == 'no': continue
        src_node = tu.find('xliff:source', namespaces=ns)
        src_txt = (src_node.text or '').strip() if src_node is not None else ''
        tgt_node = tu.find('xliff:target', namespaces=ns)
        tgt_txt = (tgt_node.text or '').strip() if tgt_node is not None else ''

        if not src_txt: continue
        
        # Check against patterns
        lower_source = src_txt.lower()
        if lower_source.endswith(('.jpg', '.png')) or lower_source in non_translatable or any(p.fullmatch(lower_source) for p in non_translatable_patterns):
            continue
        
        records.append({
            'id': tu.get('id'),
            'source': src_txt,
            'existing_target': tgt_txt,
            'gomo-id (context)': tu.get('gomo-id', '')
        })
    return pd.DataFrame(records)

def update_glossary_file(glossary_path, new_entries):
    """Updates the glossary Excel file with new entries."""
    if Path(glossary_path).exists():
        glossary_df = pd.read_excel(glossary_path)
    else:
        glossary_df = pd.DataFrame(columns=['source_text', 'target_text', 'language_code'])
        
    new_entries_df = pd.DataFrame(new_entries)
    combined_df = pd.concat([glossary_df, new_entries_df], ignore_index=True)
    combined_df.drop_duplicates(subset=['source_text', 'language_code'], keep='first', inplace=True)
    combined_df.to_excel(glossary_path, index=False)

def center_window(popup, width, height, parent):
    """
    Centers a popup window relative to the parent window.
    """
    popup.update_idletasks() # Ensure geometry data is ready
    
    # Get Parent Geometry
    root = parent.winfo_toplevel()
    root_x = root.winfo_x()
    root_y = root.winfo_y()
    root_w = root.winfo_width()
    root_h = root.winfo_height()
    
    # Calculate Center
    x = root_x + (root_w // 2) - (width // 2)
    y = root_y + (root_h // 2) - (height // 2)
    
    # Safety Check (Prevent off-screen)
    if x < 0: x = 0
    if y < 0: y = 0
    
    popup.geometry(f"{width}x{height}+{x}+{y}")
