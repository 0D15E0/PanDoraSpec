import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from .orchestrator import run_dora_audit_logic

app = typer.Typer(help="DORA Audit CLI - Verify Compliance of OpenAI Specs")
console = Console()

def run_audit(
    target: str = typer.Argument(..., help="URL or path to OpenAPI schema"),
    api_key: str = typer.Option(None, "--key", "-k", help="API Key for authenticated endpoints"),
    vendor: str = typer.Option("Vendor", "--vendor", "-v", help="Vendor name for the report"),
    config: str = typer.Option(None, "--config", "-c", help="Path to .yaml configuration file"),
    base_url: str = typer.Option(None, "--base-url", "-b", help="Override API Base URL"),
    output_format: str = typer.Option("pdf", "--format", "-f", help="Report format (pdf or json)"),
    output_path: str = typer.Option(None, "--output", "-o", help="Custom path for the output report file")
):
    """
    Run a DORA audit against an OpenAPI schema.
    """
    console.print(Panel(f"[bold blue]Starting DORA Audit for {vendor}[/bold blue]", border_style="blue"))
    console.print(f"🔎 Scanning [bold]{target}[/bold]...")

    try:
        # Delegate to Orchestrator
        audit_result = run_dora_audit_logic(
            target=target,
            vendor=vendor,
            api_key=api_key,
            config_path=config,
            base_url=base_url,
            output_format=output_format,
            output_path=output_path
        )
        
        if audit_result.seed_count > 0:
            console.print(f"[green]Loaded {audit_result.seed_count} seed values from config[/green]")
        
        results = audit_result.results

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
        
        console.print(Panel(f"[bold green]Audit Complete![/bold green]\n📄 Report generated: [link={audit_result.report_path}]{audit_result.report_path}[/link]", border_style="green"))

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

def main():
    typer.run(run_audit)

if __name__ == "__main__":
    main()
