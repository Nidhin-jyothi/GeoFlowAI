import re
import textwrap

def extract_python_code(raw_output: str) -> str:
    """
    Robustly extracts Python code from an LLM response.
    1. Looks for ```python ... ``` blocks.
    2. If not found, looks for ``` ... ``` blocks.
    3. If neither, assumes the whole text is code.
    4. Applies textwrap.dedent to clean up any leading indentation from the LLM.
    """
    # 1. Try finding ```python ... ```
    match = re.search(r"```python\s+(.*?)\s+```", raw_output, re.DOTALL | re.IGNORECASE)
    if not match:
        # 2. Try finding ``` ... ```
        match = re.search(r"```\s+(.*?)\s+```", raw_output, re.DOTALL)
    
    if match:
        code = match.group(1)
    else:
        # 3. Fallback to whole text
        code = raw_output.strip()

    # 4. Cleanup and dedent
    return textwrap.dedent(code).strip()

