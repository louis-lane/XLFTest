import pandas as pd
from lxml import etree
from pathlib import Path
from typing import Tuple, Optional, List
from utils.core import CONFIG, log_errors, get_target_language, decompress_ids
from utils.glossary import update_glossary_from_list

def import_and_reconstruct_with_glossary(root_path: Path, glossary_path: Optional[Path] = None) -> Tuple[int, int]:
    """
    Imports translations from Excel and updates the original XLIFF files.
    Splits output into language-specific folders.

    Returns:
        Tuple[int, int]: (Files Reconstructed, Error Count)
    """
    input_dir = root_path / str(CONFIG["folder_names"]["excel_export"])
    if not input_dir.exists():
        raise ValueError("Excel export folder not found.")
    
    master_files = list(input_dir.glob('*-master.xlsx'))
    if not master_files:
        raise ValueError("No master files found.")
    
    errors: List[str] = []
    
    # 1. Update Glossary from Excel inputs
    try:
        new_entries = []
        for mf in master_files:
            lc = mf.name.replace("-master.xlsx", "")
            try:
                df = pd.read_excel(mf, sheet_name=f"{lc}-Translate_Here")
                if 'add_to_glossary' in df.columns:
                    for _, row in df[df['add_to_glossary'].astype(str).str.lower().isin(['x', 'yes'])].iterrows():
                        if pd.notna(row['target']):
                            new_entries.append({
                                'source_text': row['source'],
                                'target_text': str(row['target']),
                                'language_code': lc
                            })
            except Exception:
                pass
        if new_entries and glossary_path:
            update_glossary_from_list(glossary_path, new_entries)
    except Exception as e:
        errors.append(f"Glossary update failed: {e}")

    # 2. Build Translation Map
    trans_map = {}
    for mf in master_files:
        try:
            lc = mf.name.replace("-master.xlsx", "")
            if lc not in trans_map: trans_map[lc] = {}
            
            df = pd.read_excel(mf, sheet_name=f"{lc}-Translate_Here").dropna(subset=['target', 'id_blob'])
            for _, row in df.iterrows():
                tgt = str(row['target'])
                for uid in decompress_ids(str(row['id_blob'])):
                    trans_map[lc][uid] = tgt
        except Exception as e:
            errors.append(f"Map error {mf.name}: {e}")

    # 3. Write XLIFFs
    out_dir = root_path / str(CONFIG["folder_names"]["xliff_output"])
    sep_dir = out_dir / "Separate Languages"
    out_dir.mkdir(exist_ok=True)
    sep_dir.mkdir(exist_ok=True)
    
    cnt = 0
    for xf in list(root_path.glob('*.xliff')):
        try:
            lc = get_target_language(xf)
            l_map = trans_map.get(lc, {})
            
            # Fallback for case-insensitive matching
            if not l_map:
                for k in trans_map:
                    if k.lower() == lc.lower():
                        l_map = trans_map[k]
                        break
            
            tree = etree.parse(xf)
            ns = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
            for tu in tree.xpath('//xliff:trans-unit', namespaces=ns):
                uid = tu.get('id')
                if uid in l_map:
                    tn = tu.find('xliff:target', namespaces=ns)
                    if tn is None:
                        tn = etree.SubElement(tu, f"{{{ns['xliff']}}}target")
                    tn.text = l_map[uid]
                    tn.set('state', 'translated')
            
            # Save generic copy
            tree.write(out_dir / xf.name, pretty_print=True, xml_declaration=True, encoding='UTF-8')
            
            # Save language specific copy
            (sep_dir / lc).mkdir(exist_ok=True)
            tree.write(sep_dir / lc / xf.name, pretty_print=True, xml_declaration=True, encoding='UTF-8')
            cnt += 1
        except Exception as e:
            errors.append(f"Reconstruct error {xf.name}: {e}")

    if errors: log_errors(root_path, errors)
    return cnt, len(errors)
