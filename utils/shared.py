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
    "protected_languages": ["English", "Spanish", "French", "German"] # (Truncated for brevity, logic remains)
}

def load_config():
    if getattr(sys, 'frozen', False):
        app_path = Path(sys.executable).parent
    else:
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
    # Shared parsing logic used by Analysis and Excel Export
    ns = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
    tree = etree.parse(xliff_path)
    records = []
    non_translatable = {'left-alignc', 'imagestatic-1', 'video2-1'}
    
    for tu in tree.xpath('//xliff:trans-unit', namespaces=ns):
        if tu.get('translate') == 'no': continue
        src_node = tu.find('xliff:source', namespaces=ns)
        src_txt = (src_node.text or '').strip() if src_node is not None else ''
        tgt_node = tu.find('xliff:target', namespaces=ns)
        tgt_txt = (tgt_node.text or '').strip() if tgt_node is not None else ''

        if not src_txt: continue
        if src_txt.lower() in non_translatable: continue
        
        records.append({
            'id': tu.get('id'),
            'source': src_txt,
            'existing_target': tgt_txt,
            'gomo-id (context)': tu.get('gomo-id', '')
        })
    return pd.DataFrame(records)