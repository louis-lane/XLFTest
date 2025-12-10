import pandas as pd
from pathlib import Path
from utils.core import get_target_language, xliff_to_dataframe
from utils.glossary import get_glossary_map

def perform_analysis(root_path, glossary_path=None):
    xliff_files = list(root_path.glob('*.xliff'))
    if not xliff_files: raise ValueError("No XLIFF files.")
    
    g_map = get_glossary_map(glossary_path)

    records = []
    for f in xliff_files:
        df = xliff_to_dataframe(f)
        if not df.empty:
            df['language'] = get_target_language(f)
            df['wc'] = df['source'].str.split().str.len()
            records.append(df)
            
    if not records: raise ValueError("No content.")
    mdf = pd.concat(records)
    
    results = {}
    for lc, ldf in mdf.groupby('language'):
        uniq = ldf.drop_duplicates(subset=['source'])
        reps = ldf[ldf.duplicated(subset=['source'], keep=False)]
        rep_w = reps['wc'].sum() - uniq[uniq['source'].isin(reps['source'])]['wc'].sum()
        
        lg = g_map.get(lc, {})
        match_w = uniq[uniq['source'].isin(lg.keys())]['wc'].sum()
        new_w = uniq[~uniq['source'].isin(lg.keys())]['wc'].sum()
        
        results[lc] = {'Total Words': ldf['wc'].sum(), 'Repetitions': rep_w, 'Glossary Matches': match_w, 'New Words': new_w}
    return results
