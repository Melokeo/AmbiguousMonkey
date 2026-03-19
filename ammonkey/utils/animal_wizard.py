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

def main():
    if add_animal():
        if Confirm.ask("[cyan]Add new DLC model?[/cyan]"):
            add_dlc()

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
    

if __name__ == "__main__":
    main()