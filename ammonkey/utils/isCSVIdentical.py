import pandas as pd
import hashlib
from pathlib import Path

def hashCsvContent(filePath: str | Path) -> str:
    """hash CSV content after normalizing - because who has time for line-by-line drama"""
    df = pd.read_csv(filePath)
    # sort by all columns to handle row order differences
    df_sorted = df.sort_values(by=list(df.columns)).reset_index(drop=True)
    # convert to string representation and hash
    content_str = df_sorted.to_string(index=False)
    return hashlib.sha256(content_str.encode()).hexdigest()

def areCsvFilesIdentical(file1: str | Path, file2: str | Path) -> bool:
    """compare CSV files like a boss - metadata? ain't nobody got time for that"""
    try:
        hash1 = hashCsvContent(file1)
        hash2 = hashCsvContent(file2)
        print(f'{Path(file1).stem}, {hash1=}')
        print(f'{Path(file2).stem}, {hash2=}')
        return hash1 == hash2
    except Exception as e:
        print(f"Error comparing files: {e}")
        return False

# example usage
if __name__ == "__main__":
    file1 = r"P:\projects\monkeys\Chronic_VLL\DATA\Pici\2025\03\20250321\clean\20250321-Pici-Pull-sphere-big-1.csv"
    file2 = r"P:\projects\monkeys\Chronic_VLL\DATA\Pici\2025\03\20250321\clean\20250321-Pici-Pull sphere big-1.csv"
    
    if areCsvFilesIdentical(file1, file2):
        print("Files are identical!")
    else:
        print("Files differ")