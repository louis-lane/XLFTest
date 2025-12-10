import re
import pandas as pd
from lxml import etree
from pathlib import Path
from typing import Tuple, List, Dict, Any, Union, Optional
from utils.core import get_target_language
from utils.glossary import load_glossary_as_list, find_glossary_matches

class EditorLogic:
    """
    Handles business logic for the XLIFF Editor.
    Parses files, manages tags, and interfaces with the glossary.
    """
    
    # UPDATED: Removed closing tags to declutter the UI
    STANDARD_TAGS = {
        "Gomo []": ["[b]", "[i]", "[u]", "[br/]", "[p]"], 
        "Standard XML <>": ["<b>", "<i>", "<u>", "<br/>", "<p>"]
    }

    def __init__(self):
        # ... (Rest of the logic file remains exactly the same)
        # You do not need to change the methods, just the STANDARD_TAGS list above.
        self.namespaces = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
        self.glossary_data: List[Dict[str, Any]] = []

    def load_xliff(self, path: Union[str, Path]) -> Tuple[Any, List[Dict[str, Any]]]:
        try:
            tree = etree.parse(str(path))
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

    def save_xliff(self, tree: Any, path: Union[str, Path]) -> None:
        tree.write(str(path), encoding="UTF-8", xml_declaration=True, pretty_print=True)

    def load_glossary(self, path: Union[str, Path] = "glossary.xlsx") -> None:
        self.glossary_data = load_glossary_as_list(Path(path))

    def find_glossary_matches(self, source_text: str, current_file_path: Optional[Path]) -> List[Tuple[str, str]]:
        return find_glossary_matches(source_text, current_file_path, self.glossary_data)

    def get_tag_suggestions(self, text: str, syntax_mode: str = "Standard XML <>") -> Dict[str, List[str]]:
        # 1. Get Standard Tags
        defaults = self.STANDARD_TAGS.get(syntax_mode, [])
        
        # 2. Extract Context Tags
        extracted = self.extract_tags(text, syntax_mode)
        
        # 3. Filter Context Tags (Exclude duplicates from standard list)
        defaults_lower = {t.lower() for t in defaults}
        unique_context = [t for t in extracted if t.lower() not in defaults_lower]
        
        return {
            "standard": defaults,
            "context": unique_context
        }

    def extract_tags(self, text: str, syntax_mode: str = "Standard XML <>") -> List[str]:
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
            if (tag.startswith("</") or tag.startswith("[/")):
                continue
            
            if tag not in seen:
                seen.add(tag)
                unique_openers.append(tag)
        return unique_openers
