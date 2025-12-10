import json
import sys
from pathlib import Path
from datetime import datetime
from lxml import etree
import pandas as pd
import zlib
import base64
import re
import tkinter as tk

# --- CONFIGURATION ---
DEFAULT_CONFIG = {
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

def load_config():
    if getattr(sys, 'frozen', False):
        app_path = Path(sys.executable).parent
    else:
        # Robust lookup: try parent, then parent's parent
        app_path = Path(__file__).parent.parent
        if not (app_path / "config.json").exists():
             app_path = Path(__file__).parent.parent.parent

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

# --- GUI HELPERS ---
def center_window(popup, width, height, parent):
    popup.update_idletasks()
    root = parent.winfo_toplevel()
    x = root.winfo_x() + (root.winfo_width() // 2) - (width // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (height // 2)
    if x < 0: x = 0
    if y < 0: y = 0
    popup.geometry(f"{width}x{height}+{x}+{y}")

# --- FILE HELPERS ---
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
