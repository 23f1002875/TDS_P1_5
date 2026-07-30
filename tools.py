import re
import os
import io
import requests
import zipfile
import contextlib
import pandas as pd
from typing import Dict, Tuple, Any, List

def extract_urls(text: str) -> List[str]:
    """Finds and returns all HTTP/HTTPS URLs from text, stripping markdown & trailing punctuation."""
    raw_urls = re.findall(r'https?://[^\s<>"\'\]\)]+', text)
    cleaned_urls = []
    for url in raw_urls:
        clean_url = url.rstrip(')].,;:]')
        if clean_url and clean_url not in cleaned_urls:
            cleaned_urls.append(clean_url)
    return cleaned_urls

def safe_read_csv(content: bytes) -> pd.DataFrame:
    """Attempts to read a CSV gracefully bypassing malformed lines."""
    try:
        return pd.read_csv(io.BytesIO(content), on_bad_lines='skip')
    except Exception:
        return pd.read_csv(io.BytesIO(content), encoding='latin1', on_bad_lines='skip')

def load_file_content(filename: str, content: bytes) -> Dict[str, pd.DataFrame]:
    """Parses raw bytes into Pandas DataFrame(s) based on file extension."""
    dfs = {}
    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    
    try:
        if ext == 'csv':
            dfs[filename] = safe_read_csv(content)
        elif ext in ['xls', 'xlsx']:
            excel_dfs = pd.read_excel(io.BytesIO(content), sheet_name=None)
            for sheet_name, df in excel_dfs.items():
                dfs[f"{filename}_{sheet_name}"] = df
        elif ext == 'json':
            dfs[filename] = pd.read_json(io.BytesIO(content))
        elif ext == 'html':
            html_dfs = pd.read_html(io.BytesIO(content))
            for i, df in enumerate(html_dfs):
                dfs[f"{filename}_table_{i}"] = df
        else:
            dfs[f"{filename}_fallback.csv"] = safe_read_csv(content)
    except Exception as e:
        print(f"Error parsing {filename}: {e}")
        
    return dfs

def download_and_extract(url: str, max_retries: int = 3) -> Dict[str, pd.DataFrame]:
    """
    Downloads a file from a URL. Follows redirects. 
    If it's a ZIP, extracts it and parses all recognizable files.
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, allow_redirects=True, timeout=15)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '')
            filename = url.split('/')[-1].split('?')[0]
            if not filename:
                filename = "dataset.file"

            dfs = {}
            if 'zip' in content_type.lower() or filename.endswith('.zip'):
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    for name in z.namelist():
                        if not name.endswith('/'):
                            file_bytes = z.read(name)
                            dfs.update(load_file_content(name, file_bytes))
            else:
                dfs.update(load_file_content(filename, response.content))
                
            return dfs
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                print(f"Failed to download {url}: {e}")
                return {}

    return {}

def execute_python(code: str, df_dict: Dict[str, pd.DataFrame]) -> Tuple[bool, str, Any]:
    """
    Executes Python code dynamically in a restricted local scope.
    The code must assign its final output to a variable named `result_data`.
    """
    code = code.strip()
    if code.startswith('```python'):
        code = code[9:]
    elif code.startswith('```'):
        code = code[3:]
    if code.endswith('```'):
        code = code[:-3]
    
    stdout = io.StringIO()
    local_vars = {"dfs": df_dict, "pd": pd}
    
    try:
        with contextlib.redirect_stdout(stdout):
            exec(code, {}, local_vars)
        
        result = local_vars.get("result_data")
        return True, stdout.getvalue(), result
    except Exception as e:
        # Include exception type (e.g. "KeyError: 'non_existent.csv'") for clearer debugging
        return False, f"{type(e).__name__}: {e}", None