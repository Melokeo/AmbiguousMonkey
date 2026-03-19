'''util to add a new animal to process'''

from pathlib import Path
import shutil

from ruamel.yaml import YAML
yaml = YAML(typ='safe', pure=True)

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.rule import Rule
from rich.text import Text

from ammonkey.core.config import Config

console = Console()

MODEL_YARD = r'D:\DeepLabCut'

import sys
import msvcrt

def tui_select(options: list[str], prompt: str = "Select an option:") -> str:
    from rich.live import Live
    selected = 0
    with Live(auto_refresh=False) as live:
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

def tui_multiselect(options: list[tuple[str, str]], prompt: str = "Select options:") -> list[str]:
    from rich.live import Live
    from rich.table import Table
    from rich.console import Group
    
    selected_indices = set()
    focused = 0
    
    with Live(auto_refresh=False) as live:
        while True:
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Focus", justify="center", width=2)
            table.add_column("Selected", justify="center", width=3)
            table.add_column("Option", overflow="fold")
            
            for i, (opt_id, opt_disp) in enumerate(options):
                is_focused = (i == focused)
                is_selected = i in selected_indices
                
                focus_col = ">" if is_focused else ""
                sel_col = "[green]\\[x][/green]" if is_selected else "\\[ ]"
                style = "bold cyan" if is_focused else "default"
                
                table.add_row(
                    f"[{style}]{focus_col}[/{style}]", 
                    sel_col, 
                    f"[{style}]{opt_disp}[/{style}]"
                )
            
            text_dim = "[dim](Up/Down: Move, Space: Toggle, Enter: Confirm)[/dim]"
            live.update(Panel(Group(f"[cyan]{prompt}[/cyan]", table, text_dim)))
            live.refresh()
            
            key = msvcrt.getch()
            if key == b'\xe0':
                key = msvcrt.getch()
                if key == b'H':  # Up arrow
                    focused = (focused - 1) % len(options)
                elif key == b'P':  # Down arrow
                    focused = (focused + 1) % len(options)
            elif key == b' ':  # Space
                if focused in selected_indices:
                    selected_indices.remove(focused)
                else:
                    selected_indices.add(focused)
            elif key == b'\r':  # Enter
                break
            elif key == b'\x03': # Ctrl+C
                sys.exit(0)
                
    selected_ids = [options[i][0] for i in sorted(list(selected_indices))]
    return selected_ids

def main():
    options = [
        "New Animal",
        "New DLC Model",
        "New Combo",
        "New Anipose Config",
        "All Above",
        "Quit"
    ]
    
    while True:
        choice = tui_select(options, "Select...")
        
        if choice == "New Animal":
            add_animal()
        elif choice == "New DLC Model":
            add_dlc()
        elif choice == "New Combo":
            add_combo()
        elif choice == "New Anipose Config":
            add_anipose_cfg()
        elif choice == "All Above":
            add_animal()
            while Confirm.ask("Add a new DLC model?"):
                add_dlc()
            add_combo()
        elif choice == "Quit":
            break

        console.print(Rule(style="dim"))


def add_animal() -> bool:
    console.print(Rule("[bold]New Animal[/bold]", style="cyan"))

    animal_name = Prompt.ask("[cyan]Animal name[/cyan]")
    if not animal_name:
        console.print("[bold]Skipped[/bold]")
        return True
    if Config.has_animal(animal_name):
        console.print(f"[bold yellow]{animal_name!r}[/bold yellow] already exists in config.")
        return False

    animal_path_str = Prompt.ask(
        f"[cyan]Path to animal[/cyan] [dim](.../project/DATA_RAW/{animal_name})[/dim]"
    )
    if not animal_path_str:
        console.print("[bold red]Error:[/bold red] Path cannot be empty.")
        return False
    animal_path_str = animal_path_str.strip('"')

    try:
        animal_path = Path(animal_path_str)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] Invalid path: {e}")
        return False

    if not animal_path.exists():
        console.print(f"[bold yellow]Warning:[/bold yellow] Path does not exist: [bold]{animal_path}[/bold]")
        return False

    if (not animal_path.parent.name == 'DATA_RAW' or
            not animal_path.name.lower() == animal_name.lower()):
        console.print(
            f"[bold yellow]Warning:[/bold yellow] Path should be like "
            f"[bold].../project/DATA_RAW/{animal_name}[/bold], "
            f"but got: [bold]{animal_path}[/bold]"
        )
        if not Confirm.ask("Continue?"):
            return False

    animal_name = animal_name.lower()
    Config.animals.append(animal_name)
    Config.animal_paths[animal_name] = str(animal_path)
    Config.save()
    console.print(f"[bold green]Success:[/bold green] Added [bold]{animal_name}[/bold].")

    return True


def add_dlc() -> bool:
    console.print(Rule("[bold]New DLC Model[/bold]", style="cyan"))
    model_display_name = Prompt.ask("[cyan]Model name to be displayed[/cyan]")
    if not model_display_name:
        console.print("[bold red]Error:[/bold red] Model name cannot be empty.")
        return False
    model_display_name = model_display_name.strip()

    if model_display_name in Config.dlc_models:
        console.print(f"[bold yellow]{model_display_name!r}[/bold yellow] already exists in config.")
        return False

    model_cfg_str = Prompt.ask(f"[cyan]DLC config.yaml path[/cyan]")
    if not model_cfg_str:
        console.print("[bold red]Error:[/bold red] Model path cannot be empty.")
        return False
    model_cfg_str = model_cfg_str.strip('"')
    try:
        model_cfg_path = Path(model_cfg_str)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] Invalid path: {e}")
        return False
    if not model_cfg_path.exists():
        console.print(f"[bold red]Error:[/bold red] Path does not exist: [bold]{model_cfg_path}[/bold]")
        return False
    
    if Confirm.ask('Copy'):
        dest_name = Prompt.ask("Rename the folder?", default=model_cfg_path.parent.name)
        dest = Path(MODEL_YARD) / dest_name
        #with console.status(f"Copying DLC model to [bold]{dest}[/bold]...", spinner="monkey"):
        if copy_dlc_dir(model_cfg_path.parent, dest):
            model_cfg_path = dest / model_cfg_path.name
        else:
            console.print("[bold red]Error:[/bold red] Failed to copy DLC model.")
            return False
    
    dir_name, iteration, shuffle = extract_dlc_info(model_cfg_path)
    iter_shuff = get_available_iter_shuff(model_cfg_path)

    console.print(f"DLC folders should be called {dir_name}, using iter {iteration}, shuffle {shuffle}")
    console.print(f"[dim]This model has:\n{iter_shuff}[/dim]")

    if dir_name == '??':
        console.print(f"[bold red]Failed to extract DLC info!!")
        return False

    if Confirm.ask("Assign another iter/shuffle"):
        try:
            iteration = int(Prompt.ask("Iteration", default=str(iteration)))
            shuffle = int(Prompt.ask("Shuffle", default=max(iter_shuff.get(iteration, [-99]))))
        except ValueError:
            console.print("[bold red]Error:[/bold red] Iteration and shuffle must be integers.")
            return False

    Config.dlc_models[model_display_name] = {
        'dir-name': dir_name,
        'cfg-path': str(model_cfg_path),
        'iteration': iteration,
        'shuffle': shuffle,
    }
    Config.save()

    return True

def add_combo() -> bool:
    console.print(Rule("[bold]New Combo[/bold]", style="cyan"))

    models = get_all_models()
    if not models:
        console.print("[bold red]Error:[/bold red] No DLC models available. Please add a DLC model first.")
        return False
    
    selected_models = tui_multiselect(models, "Select DLC models to combo process:")
    if not selected_models:
        console.print("[bold yellow]No models selected.[/bold yellow]")
        return False
        
    # console.print(f"[bold green]Selected models:[/bold green] {', '.join(selected_models)}")
    # The selected_models list containing model internal names is available for further use here.
    console.print(f"Will make combo: [bold cyan]{', '.join(selected_models)}[/bold cyan]")
    
    # Validation 1: Combo name must be unique
    while True:
        combo_name = Prompt.ask("[italic dim]WILL BE USED IN FINAL FOLDER NAME[/italic dim] Combo name")
        if not combo_name:
            console.print("[bold yellow] A combo name is required[/bold yellow]")
            continue
        if hasattr(Config, 'combos') and combo_name in getattr(Config, 'combos', {}):
            console.print(f"[bold yellow]Combo name '{combo_name}' already exists in config. Choose another.[/bold yellow]")
            continue
        break

    # Validation 2: Cam group names must not collide and must be valid
    combo_dict = {}
    lines_used = 1 # count for combo_name prompt
    
    valid_groups = Config.get_cam_groups()
    if not valid_groups:
        console.print("[bold red]Error: No cam groups defined in config![/bold red]")
        return False
        
    for model in selected_models:
        while True:
            avail_groups = [g for g in valid_groups if g not in combo_dict]
            groups_str = "/".join(f"[bold green]{g}[/bold green]" for g in avail_groups)
            
            key = Prompt.ask(f"Cam group name for model [bold cyan]{model}[/bold cyan] [dim](Available:[/dim] {groups_str}[dim])[/dim]")
            lines_used += 1
            if not key:
                console.print("[bold yellow] A cam group name is required[/bold yellow]")
                lines_used += 1
                continue
            if key not in valid_groups:
                console.print(f"[bold yellow]Cam group '{key}' is not defined in config. Valid groups: {', '.join(valid_groups)}[/bold yellow]")
                lines_used += 1
                continue
            if key in combo_dict:
                console.print(f"[bold yellow]Cam group name '{key}' already used for model '{combo_dict[key]}'. Choose another.[/bold yellow]")
                lines_used += 1
                continue
            combo_dict[key] = model
            break

    # flush the input lines
    lines_to_clear = 1 + lines_used
    for _ in range(lines_to_clear):
        sys.stdout.write("\033[1A\033[2K")
    sys.stdout.flush()

    # print the formatted dict
    formatted_combo = f"[bold]{combo_name}:[/bold]\n"
    for k, v in combo_dict.items():
        formatted_combo += f"  [bold]{k}:[/bold] {v}\n"
    console.print("[bold green]Will add combo:[/bold green]")
    console.print(formatted_combo.rstrip())

    # add it to config here
    if Confirm.ask("Confirm adding this combo?"):
        Config.dlc_combos[combo_name] = combo_dict
        Config.save()
    else: # flush confirm then say cancelled
        sys.stdout.write("\033[1A\033[2K")
        sys.stdout.flush()
        console.print("[dim]Cancelled combo[/dim]")

    return True


def add_anipose_cfg() -> bool:
    console.print(Rule("[bold]New Anipose Config[/bold]", style="cyan"))
    console.print("[dim]Not implemented yet...[/dim]")
    return False

def add_anipose_lib() -> bool:
    '''add a new group of anipose configs that share the same calib file (same cam setup)'''
    console.print(Rule("[bold]New Anipose Library[/bold]", style="cyan"))
    console.print("[dim]Not implemented yet...[/dim]")
    return False


def config_cam_grouping():
    '''consider write in camera_wizard.py'''
    pass


# === Helpers ===

def copy_dlc_dir(src: Path, dest: Path) -> bool:
    '''copy DLC model dir from src to dest, return success'''
    try:
        if dest.exists():
            console.print(f"[bold yellow]Warning:[/bold yellow] Destination already exists: [bold]{dest}[/bold]")
            if not Confirm.ask("Overwrite?"):
                return False
            shutil.rmtree(dest)
        with console.status(f"Copying DLC model to [bold]{dest}[/bold]...", spinner="monkey"):
            shutil.copytree(src, dest)
        console.print(f"[bold green]Success:[/bold green] Copied DLC model to [bold]{dest}[/bold]")
        return True
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to copy DLC model: {e}")
        return False

def get_available_iter_shuff(cfg_path: Path) -> dict[int, list[int]]:
    iter_shuff = {}
    models_dir = cfg_path.parent / 'dlc-models'
    for subdir in models_dir.iterdir():
        if not subdir.is_dir():
            continue
        if not subdir.name.startswith('iteration'):
            continue
        try:
            iter_num = int(subdir.name.replace('iteration-', ''))
        except ValueError:
            console.print(f"[dim]Unexpected iteration folder name: {subdir.name}[/dim]")
            continue
        shuffles = []
        for shuffle_dir in subdir.iterdir():
            if not shuffle_dir.is_dir():
                continue
            if not 'shuffle' in (sn:=shuffle_dir.name):
                continue
            try:
                shuffle_num = int(sn.split('shuffle')[-1])
            except ValueError:
                console.print(f"[dim]Unexpected shuffle folder name: {shuffle_dir.name}[/dim]")
                continue
            shuffles.append(shuffle_num)
        if shuffles:
            iter_shuff[iter_num] = shuffles
    return iter_shuff


def extract_dlc_info(cfg_path: Path) -> tuple[str, int, int]:
    '''extract dir name, iteration and shuffle from DLC config yaml'''
    try:
        with open(cfg_path) as f:
            cfg = yaml.load(f)
        if not cfg or not isinstance(cfg, dict):
            raise ValueError("Invalid DLC config format")
        
        dir_name = f"{cfg.get('Task', '??')}{cfg.get('date', '??')}"
        iteration = int(cfg.get('iteration', 0))

        shuffles = get_available_iter_shuff(cfg_path)
        if not iteration in shuffles.keys():
            console.print(f"[yellow]No shuffle folders found for iteration {iteration}![/yellow]")
            shuffle = -99
        else:
            shuffle = max(shuffles[iteration])

        return dir_name, iteration, shuffle
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to extract DLC info: {e}")
        return '??', -99, -99
    
def get_all_models() -> list[tuple[str, str]]:
    '''get all DLC models in the config for making combo'''
    models = []
    for name, info in Config.dlc_models.items():
        models.append((name, f"{name} [dim](iter {info['iteration']}, shuffle {info['shuffle']})[/dim]"))

    return models

if __name__ == "__main__":
    main()