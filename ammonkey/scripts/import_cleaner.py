import os
import re
import argparse
from collections import defaultdict

def find_python_files(directory: str) -> list[str]:
    """
    Recursively finds all Python files (ending with .py) in a given directory.

    Args:
        directory (str): The path to the directory to search.

    Returns:
        list[str]: A list of paths to all found Python files.
    """
    python_files: list[str] = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    return python_files

def extract_imports(file_path: str) -> list[str]:
    """
    Extracts all import statements from a single Python file.

    Args:
        file_path (str): The path to the Python file.

    Returns:
        list[str]: A list of unique import statements found in the file.
    """
    # Regex to find import statements, including from ... import ...
    # This will capture the entire line.
    import_regex = re.compile(r"^\s*(import .+|from .+\s+import .+)$", re.MULTILINE)
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content: str = f.read()
            imports: list[str] = import_regex.findall(content)
            # Clean up and remove duplicates
            return sorted(list(set([imp.strip() for imp in imports])))
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []

def main() -> None:
    """
    Main function to drive the script.
    Parses arguments, finds files, extracts imports, and prints the report.
    """
    parser = argparse.ArgumentParser(
        description="Scan a directory for Python files and collect all import statements."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="The directory to scan. Defaults to the current directory.",
    )
    args = parser.parse_args()

    target_directory: str = args.directory
    if not os.path.isdir(target_directory):
        print(f"Error: Directory '{target_directory}' not found.")
        return

    print(f"Scanning for Python files in '{os.path.abspath(target_directory)}'...\n")
    
    python_files: list[str] = find_python_files(target_directory)
    
    if not python_files:
        print("No Python files found.")
        return

    all_imports: set[str] = set()
    imports_by_file: defaultdict[str, list[str]] = defaultdict(list)

    for py_file in python_files:
        imports: list[str] = extract_imports(py_file)
        if imports:
            imports_by_file[py_file] = imports
            all_imports.update(imports)

    if not all_imports:
        print("Found Python files, but no import statements were detected.")
        return

    print("---" * 10)
    print("      Unique Import Statements Found (Across All Files)      ")
    print("---" * 10)
    for imp in sorted(list(all_imports)):
        print(imp)
    print("\n")

    print("---" * 10)
    print("            Imports Broken Down by File            ")
    print("---" * 10)
    for file_path, file_imports in imports_by_file.items():
        relative_path = os.path.relpath(file_path, target_directory)
        print(f"\n{relative_path}:")
        for imp in file_imports:
            print(f"    - {imp}")

if __name__ == "__main__":
    main()
