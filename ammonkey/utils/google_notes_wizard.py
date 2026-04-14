'''TUI wizard for downloading and dispatching Google Drive Excel notes.'''

import json
import sys
import msvcrt
import tempfile
import shutil
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.rule import Rule

from ammonkey.utils.xlsx_from_google import (
    load_note_config, get_oauth_credentials, verify_access,
    download_shared_excel_file
)
from ammonkey.utils.excel_extract_sheets import (
    copy_excel_tabs_to_files, dispatch_files
)

console = Console()
CRED_DIR = Path(__file__).parent / 'google_cred'


def tui_select(options: list[str], prompt: str = "Select:") -> str:
    from rich.live import Live
    selected = 0
    with Live(auto_refresh=False, transient=True) as live:
        while True:
            text = f"[cyan]{prompt}[/cyan]\n"
            for i, opt in enumerate(options):
                if i == selected:
                    text += f"  [bold green]> {opt}[/bold green]\n"
                else:
                    text += f"    {opt}\n"
            text = text.rstrip()
            live.update(Panel(text))
            live.refresh()
            
            key = msvcrt.getch()
            if key == b'\xe0':
                key = msvcrt.getch()
                if key == b'H':  # Up arrow
                    selected = (selected - 1) % len(options)
                elif key == b'P':  # Down arrow
                    selected = (selected + 1) % len(options)
            elif key == b'\r':  # Enter
                break
            elif key == b'\x03': # Ctrl+C
                sys.exit(0)
    
    console.print(f"[cyan]{prompt}[/cyan] [bold green]{options[selected]}[/bold green]")
    return options[selected]


def get_available_configs() -> dict[str, Path]:
    """Find valid JSON configs in google_cred dir."""
    CRED_DIR.mkdir(parents=True, exist_ok=True)
    configs = {}
    for json_file in CRED_DIR.glob('*.json'):
        if json_file.name == 'client_secret_1050753027000-deom7qiq1gjm2if6e2bfdnmt0gjvu2pr.apps.googleusercontent.com.json':
            continue
        try:
            config = load_note_config(json_file)
            # Try to get display name
            raw_data = json.loads(json_file.read_text(encoding='utf-8'))
            display_name = raw_data.get("name", json_file.stem)
            key = f"{display_name} ({json_file.name})"
            configs[key] = json_file
        except (ValueError, FileNotFoundError, json.JSONDecodeError):
            pass
    return configs


def _plan_destination_dirs(
    source_dir: Path,
    output_dir: Path,
    prefix: str
) -> tuple[set[Path], set[Path], int, list[str], list[str]]:
    """Return (existing_dirs, missing_dirs, existing_target_files_count, files_to_copy, missing_dates)."""
    existing_dirs: set[Path] = set()
    missing_dirs: set[Path] = set()
    existing_target_files = 0
    files_to_copy: list[str] = []
    missing_dates: list[str] = []
    is_dest_year_dir = output_dir.name.isdigit() and len(output_dir.name) == 4

    for file_path in source_dir.glob("*.xlsx"):
        filename = file_path.stem
        if len(filename) != 8 or not filename.isdigit():
            continue

        year = filename[:4]
        month = filename[4:6]
        if is_dest_year_dir:
            if year != output_dir.name:
                continue
            target_dir = output_dir / month / filename
        else:
            target_dir = output_dir / year / month / filename

        target_file = target_dir / f"{prefix}_{filename}.xlsx"

        if target_dir.exists():
            existing_dirs.add(target_dir)
        else:
            missing_dirs.add(target_dir)
            missing_dates.append(filename)

        if target_file.exists():
            existing_target_files += 1
        elif target_dir.exists():
            files_to_copy.append(filename)

    files_to_copy = sorted(files_to_copy)
    missing_dates = sorted(set(missing_dates))
    return existing_dirs, missing_dirs, existing_target_files, files_to_copy, missing_dates


def run_pipeline(config_path: Path):
    """Run the download/dispatch pipeline for a selected config."""
    try:
        note_config = load_note_config(config_path)
    except Exception as e:
        console.print(f"[bold red]Config error:[/bold red] {e}")
        return

    file_id = note_config["file_id"]
    output_dir = note_config["output_dir"]
    note_prefix = note_config["output_prefix"]

    metadata = verify_access(file_id)
    if not metadata:
        console.print("[bold red]Cannot access file or get metadata.[/bold red]")
        return

    temp_dir = None
    temp_file = None
    try:
        temp_dir = Path(tempfile.mkdtemp())
        temp_file = download_shared_excel_file(file_id, temp_dir=temp_dir)
        copy_excel_tabs_to_files(temp_file, temp_dir)

        existing_dirs, missing_dirs, existing_files, files_to_copy, missing_dates = _plan_destination_dirs(
            temp_dir,
            Path(output_dir),
            note_prefix,
        )
        files_preview = ", ".join(files_to_copy)
        # if len(files_to_copy) > 8:
        #     files_preview += ", ..."
        if not files_preview:
            files_preview = "(none)"

        site_lines = [
            f"[bold]Config:[/bold] {config_path.name}",
            f"[bold]Output Root:[/bold] {output_dir}",
            f"[bold]Output Prefix:[/bold] {note_prefix}",
            "Access OK",
            "",
        ]
        if len(missing_dirs) > 0:
            missing_preview = ", ".join(missing_dates[:8])
            if len(missing_dates) > 8:
                missing_preview += ", ..."
            site_lines.append(
                f"[red]Target dir missing: {len(missing_dirs)} ({missing_preview})[/red]"
            )
        site_lines.append(
            f"[bold]Target file existing/to copy:[/bold] {existing_files}/[cyan]{len(files_to_copy)}[/cyan]"
        )
        site_lines.append(f"[bold]Files to be copied:[/bold] [cyan]{files_preview}[/cyan]")
        site_line = "\n".join(site_lines)
        console.print(Panel(site_line, title="Run Summary", border_style="cyan"))

        if not files_to_copy:
            console.print("[bold green]No new files to copy. Done.[/bold green]")
            return

        if not Confirm.ask("Proceed with dispatch?"):
            console.print("[dim]Cancelled before dispatch.[/dim]")
            return
        
        console.print('[bold]Now organizing notes to dest folders...[/bold]')
        dispatch_files(temp_dir, output_dir, prefix=note_prefix)
    
    except FileNotFoundError as e:
        console.print(f'[bold red]File not found:[/bold red] {e}. Did you map the P: drive?')
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
    finally:
        if temp_file is not None:
            temp_file.unlink(missing_ok=True)
            console.print(f"[dim]Cleaned up {temp_file}[/dim]")
        if temp_dir is not None and temp_dir.exists():
            shutil.rmtree(temp_dir)
            console.print(f"[dim]Cleaned up {temp_dir}[/dim]")


def main():
    while True:
        configs = get_available_configs()
        options = []
        if configs:
            options.extend(configs.keys())
        options.extend([
            "Check Google Credentials",
            "Add New Config",
            "Quit"
        ])
        
        choice = tui_select(options, "Select Action or Config to Run:")
        
        if choice in configs:
            run_pipeline(configs[choice])
        elif choice == "Check Google Credentials":
            check_credentials()
        elif choice == "Add New Config":
            add_config()
        elif choice == "Quit":
            break

        console.print(Rule(style="dim"))


def check_credentials():
    console.print(Rule("[bold]Check Google Credentials[/bold]", style="cyan"))
    try:
        creds = get_oauth_credentials()
        if creds and getattr(creds, 'valid', False):
            console.print("[bold green]✓ Credentials are valid.[/bold green]")
        else:
            console.print("[bold red]✗ Credentials exist but are invalid.[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Error checking credentials:[/bold red] {e}")


def add_config():
    console.print(Rule("[bold]New Notes Config[/bold]", style="cyan"))

    name = Prompt.ask("[cyan]Display Name[/cyan]")
    if not name:
        console.print("[bold]Skipped[/bold]")
        return
    
    filename = Prompt.ask("[cyan]Config filename (e.g. fusillo)[/cyan]")
    if not filename:
        console.print("[bold]Skipped[/bold]")
        return
    if not filename.endswith('.json'):
        filename += '.json'
    
    file_id = Prompt.ask("[cyan]Google Drive File ID[/cyan]")
    if not file_id:
        console.print("[bold]Skipped[/bold]")
        return
    
    out_dir = Prompt.ask(r"[cyan]Output Directory (e.g. P:\projects\...)[/cyan]")
    if not out_dir:
        console.print("[bold]Skipped[/bold]")
        return
    
    prefix = Prompt.ask("[cyan]Output File Prefix (e.g. RISO)[/cyan]")
    if not prefix:
        console.print("[bold]Skipped[/bold]")
        return

    config_path = CRED_DIR / filename
    if config_path.exists():
        if not Confirm.ask(f"[bold yellow]{filename}[/bold yellow] already exists. Overwrite?"):
            return

    data = {
        "name": name,
        "file_id": file_id,
        "output_dir": out_dir,
        "output_prefix": prefix
    }

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(data, indent=4), encoding='utf-8')
        console.print(f"[bold green]Success:[/bold green] Created [bold]{filename}[/bold].")
    except Exception as e:
        console.print(f"[bold red]Failed to save config:[/bold red] {e}")


if __name__ == "__main__":
    main()
