import typer
import yaml
import os
from rich.console import Console
from rich.prompt import Prompt, Confirm

console = Console()

def run_init_wizard(output_file: str = "pandoraspec.yaml"):
    """
    Interactive wizard to create a PanDoraSpec configuration file.
    """
    console.print("[bold blue]Welcome to the PanDoraSpec Configuration Wizard![/bold blue]")
    console.print("This will help you generate a configuration file for your API audits.\n")

    # 1. Target URL
    target = Prompt.ask("What is the [bold]Target URL[/bold] of your OpenAPI spec?", default="https://petstore.swagger.io/v2/swagger.json")

    # 2. Vendor Name
    vendor = Prompt.ask("What is the [bold]Vendor Name[/bold]?", default="MyVendor")

    # 3. API Key (Optional)
    api_key_env = Prompt.ask("Env variable name for API Key? (Leave empty to skip)", default="")
    
    # 4. Seed Data template?
    include_seed = Confirm.ask("Do you want to include a template for Seed Data?", default=True)

    # Build the config dictionary
    config_data = {
        "target": target,
        "vendor": vendor,
    }

    if api_key_env:
        config_data["api_key_env"] = api_key_env

    if include_seed:
         config_data["seed_data"] = {
            "general": {
                "limit": 10,
                "offset": 0
            },
            "verbs": {
                "POST": {
                    "dry_run": True
                }
            },
            "endpoints": {
                "/example/path": {
                    "GET": {
                        "param_name": "example_value"
                    }
                }
            }
        }

    # Write to file
    if os.path.exists(output_file):
        overwrite = Confirm.ask(f"File [bold]{output_file}[/bold] already exists. Overwrite?", default=False)
        if not overwrite:
            console.print("[yellow]Aborted.[/yellow]")
            return

    try:
        with open(output_file, "w") as f:
            yaml.dump(config_data, f, sort_keys=False, default_flow_style=False)
        
        console.print(f"\n[bold green]Success![/bold green] Configuration written to [bold]{output_file}[/bold]")
        console.print(f"Run your audit with: [cyan]pandoraspec {target} --config {output_file}[/cyan]")
        
    except Exception as e:
        console.print(f"[bold red]Error writing file:[/bold red] {e}")
