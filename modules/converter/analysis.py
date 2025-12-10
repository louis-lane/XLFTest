import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Any
from utils.core import get_target_language, xliff_to_dataframe
from utils.glossary import get_glossary_map

def perform_analysis(root_path: Path, glossary_path: Optional[Path] = None) -> Dict[str, Dict[str, int]]:
    """
    Analyzes all XLIFF files in the root_path.
    Calculates word counts, repetitions, and glossary matches.

    Args:
        root_path (Path): The directory containing .xliff files.
        glossary_path (Optional[Path]): Path to the glossary excel file.

    Returns:
        Dict: Structure { 'Language': { 'Total Words': int, ... } }
    """
    xliff_files = list(root_path.glob('*.xliff'))
    if not xliff_files:
        raise ValueError("No XLIFF files.")
    
    g_map = get_glossary_map(glossary_path)

    records = []
    for f in xliff_files:
        df = xliff_to_dataframe(f)
        if not df.empty:
            df['language'] = get_target_language(f)
            df['wc'] = df['source'].str.split().str.len()
            records.append(df)
            
    if not records:
        raise ValueError("No content.")
    mdf = pd.concat(records)
    
    results = {}
    for lc, ldf in mdf.groupby('language'):
        uniq = ldf.drop_duplicates(subset=['source'])
        reps = ldf[ldf.duplicated(subset=['source'], keep=False)]
        
        # Calculate Repetition Savings
        rep_w = reps['wc'].sum() - uniq[uniq['source'].isin(reps['source'])]['wc'].sum()
        
        lg = g_map.get(lc, {})
        # Calculate Glossary Savings
        match_w = uniq[uniq['source'].isin(lg.keys())]['wc'].sum()
        new_w = uniq[~uniq['source'].isin(lg.keys())]['wc'].sum()
        
        results[lc] = {
            'Total Words': int(ldf['wc'].sum()),
            'Repetitions': int(rep_w),
            'Glossary Matches': int(match_w),
            'New Words': int(new_w)
        }
    return results
