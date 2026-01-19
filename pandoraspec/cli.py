import typer
import yaml
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from .core import AuditEngine
from .reporting import generate_report

app = typer.Typer(help="DORA Audit CLI - Verify Compliance of OpenAI Specs")
console = Console()

def load_config(config_path: str):
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return {}

def run_audit(
    target: str = typer.Argument(..., help="URL or path to OpenAPI schema"),
    api_key: str = typer.Option(None, "--key", "-k", help="API Key for authenticated endpoints"),
    vendor: str = typer.Option("Vendor", "--vendor", "-v", help="Vendor name for the report"),
    config: str = typer.Option(None, "--config", "-c", help="Path to .yaml configuration file"),
    base_url: str = typer.Option(None, "--base-url", "-b", help="Override API Base URL")
):
    """
    Run a DORA audit against an OpenAPI schema.
    """
    console.print(Panel(f"[bold blue]Starting DORA Audit for {vendor}[/bold blue]", border_style="blue"))
    console.print(f"🔎 Scanning [bold]{target}[/bold]...")

    # Load Config
    seed_data = {}
    if config:
        config_data = load_config(config)
        seed_data = config_data.get("seed_data", {})
        
        if seed_data:
            console.print(f"[green]Loaded {len(seed_data)} seed values from {config}[/green]")

    try:
        # Pass seed_data to Engine
        engine = AuditEngine(target=target, api_key=api_key, seed_data=seed_data, base_url=base_url)
        
        results = engine.run_full_audit()
        
        # Display Summary Table
        table = Table(title="Audit Summary")
        table.add_column("Module", style="cyan", no_wrap=True)
        table.add_column("Status", style="bold")
        table.add_column("Issues (Pass/Fail)", style="magenta")

        # Drift
        drift_pass = len([r for r in results["drift_check"] if r.get("status") == "PASS"])
        drift_fail = len([r for r in results["drift_check"] if r.get("status") != "PASS"])
        drift_status = "[bold red]FAIL[/bold red]" if drift_fail > 0 else "[bold green]PASS[/bold green]"
        table.add_row("Module A: Integrity", drift_status, f"{drift_pass} / {drift_fail}")

        # Resilience
        res_pass = len([r for r in results["resilience"] if r.get("status") == "PASS"])
        res_fail = len([r for r in results["resilience"] if r.get("status") != "PASS"])
        res_status = "[bold red]FAIL[/bold red]" if res_fail > 0 else "[bold green]PASS[/bold green]"
        table.add_row("Module B: Resilience", res_status, f"{res_pass} / {res_fail}")

        # Security
        sec_pass = len([r for r in results["security"] if r.get("status") == "PASS"])
        sec_fail = len([r for r in results["security"] if r.get("status") != "PASS"])
        sec_status = "[bold red]FAIL[/bold red]" if sec_fail > 0 else "[bold green]PASS[/bold green]"
        table.add_row("Module C: Security", sec_status, f"{sec_pass} / {sec_fail}")

        console.print(table)

        # Generate Report
        report_path = generate_report(vendor, results)
        
        console.print(Panel(f"[bold green]Audit Complete![/bold green]\n📄 Report generated: [link={report_path}]{report_path}[/link]", border_style="green"))

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

def main():
    typer.run(run_audit)

if __name__ == "__main__":
    main()
