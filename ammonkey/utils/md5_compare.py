import hashlib
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

def calculate_md5(file_path: Path, chunk_size: int) -> str | None:
    """
    Calculate the MD5 hash of a file efficiently using chunks.
    """
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            # Read the file in chunks to balance memory usage and I/O speed
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        console.print(f"[bold red]Error reading {file_path}:[/bold red] {e}")
        return None

def check_file_integrity(
    directories: list[str | Path], 
    chunk_size: int = 8 * 1024 * 1024,
    recursive: bool = False,
    recursive_filter: str = '*'
) -> None:
    """
    Checks given directories. Mismatches get a detailed table; 
    passed and unique files get printed as compact strings.
    """
    file_tracker: dict[str, list[tuple[Path, str]]] = {}
    
    with console.status("[cyan]Calculating MD5...[/cyan]", spinner="monkey"):
        # 1. Collect files and calculate hashes (non-recursive)
        for dir_path in directories:
            p = Path(dir_path)
            if not p.is_dir():
                console.print(f"[yellow]Warning: '{dir_path}' is not a directory. Skipping.[/yellow]")
                continue

            files_to_check = p.rglob(recursive_filter) if recursive else p.iterdir()

            for file_path in files_to_check:
                if file_path.is_file():
                    file_md5 = calculate_md5(file_path, chunk_size)
                    if file_md5 is not None:
                        file_tracker.setdefault(file_path.name, []).append((file_path, file_md5))

        # 2. Categorize files
        mismatches: dict[str, list[tuple[Path, str]]] = {}
        passed: dict[str, list[tuple[Path, str]]] = {}
        no_match: dict[str, tuple[Path, str]] = {}

        for file_name, entries in file_tracker.items():
            if len(entries) == 1:
                no_match[file_name] = entries[0]
            else:
                unique_hashes = {md5 for _, md5 in entries}
                if len(unique_hashes) > 1:
                    mismatches[file_name] = entries
                else:
                    passed[file_name] = entries

    # 3. Report
    if not file_tracker:
        console.print("[yellow]No files were found in the provided directories.[/yellow]")
        return

    # Mismatches
    if mismatches:
        table_mismatch = Table(
            title="Mismatches", 
            show_header=True, 
            header_style="bold italic", 
            show_lines=True
        )
        table_mismatch.add_column("Filename", style="cyan")
        table_mismatch.add_column("File Path", style="dim")
        table_mismatch.add_column("MD5 Hash", style="dim")
        
        for file_name, entries in mismatches.items():
            for i, (path, md5) in enumerate(entries):
                table_mismatch.add_row(file_name if i == 0 else "", str(path), md5)
        console.print(table_mismatch)
        console.print()

    # Passed
    if passed:
        console.print("[bold green]Passed Files:[/bold green]")
        console.print(", ".join(sorted(passed.keys())), style="green")
        console.print()

    # No Match
    if no_match:
        console.print("[bold blue]No Match Files:[/bold blue]")
        console.print(", ".join(sorted(no_match.keys())), style="blue")

if __name__ == "__main__":
    check_file_integrity([
        r'C:\Users\mkrig\AppData\Local\anaconda3\envs\amm\Lib\site-packages\ammonkey\core',
        r'C:\Users\mkrig\Documents\GitHub\AmbiguousMonkey\ammonkey\core',
        r'C:\Users\mkrig\AppData\Local\anaconda3\envs\ammo1\Lib\site-packages\ammonkey\core',
    ])