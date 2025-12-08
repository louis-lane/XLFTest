import pandas as pd
from lxml import etree
from pathlib import Path
from utils.shared import get_target_language

class EditorLogic:
    def __init__(self):
        self.namespaces = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
        self.glossary_data = []

    def load_xliff(self, path):
        """Parses an XLIFF file and returns a list of record dicts."""
        try:
            tree = etree.parse(path)
            data = []
            for tu in tree.xpath('//xliff:trans-unit', namespaces=self.namespaces):
                uid = tu.get('id')
                src_node = tu.find('xliff:source', namespaces=self.namespaces)
                src = (src_node.text or "") if src_node is not None else ""
                
                tgt_node = tu.find('xliff:target', namespaces=self.namespaces)
                tgt = (tgt_node.text or "") if tgt_node is not None else ""
                
                # Default status is 'new' if not present
                status = tgt_node.get('state', 'new') if tgt_node is not None else 'new'
                
                data.append({
                    'id': uid,
                    'source': src,
                    'target': tgt,
                    'status': status,
                    # We store the XML node to make saving faster later
                    'node': tu 
                })
            return tree, data
        except Exception as e:
            raise ValueError(f"Could not parse XLIFF: {e}")

    def save_xliff(self, tree, path):
        """Writes the XML tree back to disk."""
        tree.write(path, encoding="UTF-8", xml_declaration=True, pretty_print=True)

    def load_glossary(self, path="glossary.xlsx"):
        """Loads glossary into memory."""
        self.glossary_data = []
        if not Path(path).exists(): return
        
        try:
            df = pd.read_excel(path).fillna("")
            for _, row in df.iterrows():
                # Validate minimal data
                if str(row.get('source_text', '')).strip() and str(row.get('target_text', '')).strip():
                    self.glossary_data.append({
                        "source": str(row['source_text']).strip(),
                        "target": str(row['target_text']).strip(),
                        "lang": str(row.get('language_code', '')).strip(),
                        "match_type": str(row.get('match_type', 'partial')).strip(),
                        "case_sensitive": str(row.get('case_sensitive', 'FALSE')).strip().upper() == 'TRUE',
                        "context": str(row.get('context', '')).strip(),
                        "is_forbidden": str(row.get('is_forbidden', 'FALSE')).strip().upper() == 'TRUE'
                    })
        except Exception as e:
            print(f"Glossary Error: {e}")

    def extract_tags(self, text):
        """Finds tags (e.g. <g id="1">) or variables ({name}) in text."""
        if not text: return []
        # Matches: <tag>, </tag>, {variable}, %s, %d
        pattern = r"(<\/?[a-zA-Z0-9_\-]+[^>]*>|{[^}]+}|%[sd])"
        return list(set(re.findall(pattern, text))) # Return unique tags

    def find_glossary_matches(self, source_text, current_file_path):
        """Returns a list of matching terms [(term, translation), ...]"""
        matches = []
        if not self.glossary_data or not source_text: return matches

        current_lang = "unknown"
        if current_file_path: current_lang = get_target_language(current_file_path)
        source_lower = source_text.lower()

        for entry in self.glossary_data:
            if entry['is_forbidden']: continue
            
            # Language Check
            if entry['lang'] and current_lang != "unknown":
                if not current_lang.lower().startswith(entry['lang'].lower()): continue

            # Matching Logic
            term = entry['source']
            is_match = False
            
            if entry['match_type'] == 'exact':
                if entry['case_sensitive']: is_match = (term == source_text)
                else: is_match = (term.lower() == source_lower)
            # Add Regex support if needed here
            else: # Partial
                if entry['case_sensitive']: is_match = (term in source_text)
                else: is_match = (term.lower() in source_lower)

            if is_match:
                matches.append((term, entry['target']))
        
        return matches
