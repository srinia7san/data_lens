import ast
import re

FORBIDDEN = {"os", "sys", "subprocess", "shutil"}

def validate_code_node(state):
    # 1. Sanitize: Remove markdown backticks first
    raw_code = state["code"]
    cleaned_code = re.sub(r"```python|```", "", raw_code).strip()
    
    # 2. Parse the cleaned code
    try:
        tree = ast.parse(cleaned_code)
    except SyntaxError as e:
        raise ValueError(f"Invalid Python syntax: {e}")

    # 3. Security Check: Walk the AST for imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in FORBIDDEN:
                    raise ValueError(f"Forbidden import: {alias.name}")
        
        # Security Tip: Also check for 'from x import y'
        elif isinstance(node, ast.ImportFrom):
            if node.module in FORBIDDEN:
                raise ValueError(f"Forbidden import: {node.module}")

    # Update state with cleaned code for subsequent nodes
    return {**state, "code": cleaned_code}