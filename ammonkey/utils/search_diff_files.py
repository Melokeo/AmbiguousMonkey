import hashlib
from collections import defaultdict
from pathlib import Path
from tqdm import tqdm

def get_unique_files(directory: str, filename: str) -> list[str]:
    """
    Finds files matching `filename` in `directory` and returns a list of paths
    representing unique file contents (one representative per unique content).
    """
    size_to_paths = defaultdict(list)
    
    # Step 1: Find all files matching the name and group them by size
    for filepath in tqdm(Path(directory).rglob(filename), desc="Finding files"):
        # Enforce strict case matching (helpful on Windows where rglob might be case-insensitive)
        if filepath.is_file() and filepath.name == filename:
            try:
                size = filepath.stat().st_size
                size_to_paths[size].append(filepath)
            except OSError:
                continue  # Skip unreadable files or broken symlinks
                
    unique_representatives = []
    
    # Step 2: Determine unique content
    for size, paths in tqdm(size_to_paths.items(), desc="Checking uniqueness"):
        if len(paths) == 1:
            # If it's the only file of this size, its content is guaranteed unique
            unique_representatives.append(str(paths[0]))
        else:
            # If there are size collisions, hash the files to identify distinct content
            seen_hashes = set()
            for filepath in paths:
                try:
                    # Using blake2b: it is highly optimized and significantly 
                    # faster than SHA-256 or MD5 on 64-bit systems.
                    file_hash = hashlib.blake2b()
                    
                    with open(filepath, 'rb') as f:
                        # Read in 64KB chunks to keep memory usage low for large files
                        while chunk := f.read(65536):
                            file_hash.update(chunk)
                    
                    digest = file_hash.hexdigest()
                    
                    # Store only the first file we see for each unique hash
                    if digest not in seen_hashes:
                        seen_hashes.add(digest)
                        unique_representatives.append(str(filepath))
                except OSError:
                    continue  # Skip files that fail to open during hashing
                    
    return unique_representatives

# Example Usage:
# unique_files = get_unique_files("/path/to/search/dir", "config.json")
# print(unique_files)

if __name__ == "__main__":
    search_dir = (r'P:\projects\monkeys\Chronic_VLL\DATA\Pici\2025\04')
    filename = "config.toml"
    unique_files = get_unique_files(search_dir, filename)
    print(f'Found {len(unique_files)} unique {filename} files:')

    for file in unique_files:
        print('\t' + str(file))