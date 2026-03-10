def extract_python_code(raw_output: str) -> str:
    """
    Extracts Python code from an LLM output enclosed in ```python ... ``` or ``` ... ```.

    Parameters:
        raw_output (str): The full text response from the LLM.

    Returns:
        str: Clean Python code string.
    """
    if raw_output.startswith("```python"):
        return raw_output.strip()[9:-3].strip()
    elif raw_output.startswith("```"):
        return raw_output.strip()[3:-3].strip()
    else:
        return raw_output.strip()
