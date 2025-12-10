import pandas as pd
from lxml import etree
from pathlib import Path
from utils.shared import get_target_language
from utils.glossary import load_glossary_as_list, find_glossary_matches
import re

class EditorLogic:
    def __init__(self):
        self.namespaces = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
        self.glossary_data = []

    def load_xliff(self, path):
        try:
            tree = etree.parse(path)
            data = []
            for tu in tree.xpath('//xliff:trans-unit', namespaces=self.namespaces):
                uid = tu.get('id')
                src_node = tu.find('xliff:source', namespaces=self.namespaces)
                src = (src_node.text or "") if src_node is not None else ""
                
                tgt_node = tu.find('xliff:target', namespaces=self.namespaces)
                tgt = (tgt_node.text or "") if tgt_node is not None else ""
                
                status = tgt_node.get('state', 'new') if tgt_node is not None else 'new'
                
                data.append({
                    'id': uid, 'source': src, 'target': tgt, 'status': status, 'node': tu 
                })
            return tree, data
        except Exception as e:
            raise ValueError(f"Could not parse XLIFF: {e}")

    def save_xliff(self, tree, path):
        tree.write(path, encoding="UTF-8", xml_declaration=True, pretty_print=True)

    def load_glossary(self, path="glossary.xlsx"):
        # REFACTORED: Delegated to utils/glossary.py
        self.glossary_data = load_glossary_as_list(path)

    def find_glossary_matches(self, source_text, current_file_path):
        # REFACTORED: Delegated to utils/glossary.py
        return find_glossary_matches(source_text, current_file_path, self.glossary_data)

    def extract_tags(self, text, syntax_mode="Standard XML <>"):
        if not text: return []
        patterns = {
            "Standard XML <>": r"(<[^>/]+[^>]*>|{[^}]+}|%[sd])",  
            "Gomo []": r"(\[[^\]/]+\]|{[^}]+}|%[sd])" 
        }
        pattern = patterns.get(syntax_mode, patterns["Standard XML <>"])
        raw_matches = re.findall(pattern, text)
        unique_openers = []
        seen = set()
        for tag in raw_matches:
            if tag.startswith("</") or tag.startswith("[/"): continue
            if tag not in seen:
                seen.add(tag); unique_openers.append(tag)
        return unique_openers
