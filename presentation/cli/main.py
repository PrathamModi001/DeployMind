"""DeployMind CLI - Main entry point.

Production CLI for deploying applications with AI-powered deployment pipeline.
"""

import sys
from pathlib import Path
import platform

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from rich.layout import Layout
from rich import box
from datetime import datetime
import time

from config.settings import Settings
from config.dependencies import container
from config.config_loader import ConfigLoader
from application.use_cases.full_deployment_workflow import (
    FullDeploymentWorkflow,
    FullDeploymentRequest,
)
from application.analytics.deployment_analytics import DeploymentAnalytics
from core.logger import get_logger

# Configure console for Windows compatibility
# Use legacy_windows=False to avoid Unicode spinner issues on Windows
console = Console(legacy_windows=False, force_terminal=True)
logger = get_logger(__name__)


@click.group()
@click.version_option(version="1.0.0", prog_name="deploymind")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output for debugging")
@click.option("--json", is_flag=True, help="Output results in JSON format")
@click.pass_context
def cli(ctx, verbose, json):
    """DeployMind - AI-Powered Deployment Platform

    Deploy applications to AWS EC2 with automatic security scanning,
    Docker image building, and health check monitoring.

    \b
    Examples:
      deploymind deploy -r user/app -i i-abc123
      deploymind status abc123def
      deploymind list --limit 20
      deploymind analytics --days 7
    """
    # Store global flags in context
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['json'] = json


@cli.command(name="deploy")
@click.option(
    "--repository", "-r",
    help="GitHub repository in format 'owner/repo'"
)
@click.option(
    "--instance", "-i",
    help="AWS EC2 instance ID (e.g., i-1234567890abcdef0)"
)
@click.option(
    "--port", "-p",
    type=int,
    help="Application port (default: 8080)"
)
@click.option(
    "--health-path",
    help="Health check endpoint path (default: /health)"
)
@click.option(
    "--strategy",
    type=click.Choice(["rolling", "blue-green", "canary"]),
    help="Deployment strategy (default: rolling)"
)
@click.option(
    "--environment",
    type=click.Choice(["development", "staging", "production"]),
    help="Target environment (default: production)"
)
@click.option(
    "--profile",
    help="Use deployment profile from config file"
)
@click.option(
    "--config",
    help="Path to configuration file (default: .deploymind.yml)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulate deployment without actually deploying"
)
@click.pass_context
def deploy(ctx, repository, instance, port, health_path, strategy, environment, profile, config, dry_run):
    """Deploy an application to EC2 with full deployment pipeline.

    Example:
        deploymind deploy --repository user/app --instance i-abc123def456
        deploymind deploy --profile dev
        deploymind deploy --profile prod --repository user/override-repo
    """
    try:
        # Load configuration
        config_loader = ConfigLoader(config_path=config)
        config_obj = config_loader.load()

        # Merge config with CLI arguments
        merged = config_loader.merge_with_cli_args(
            repository=repository,
            instance=instance,
            port=port,
            strategy=strategy,
            environment=environment,
            profile=profile
        )

        # Validate required fields
        if not merged.get('repository'):
            raise click.UsageError("--repository is required (or set in config/profile)")
        if not merged.get('instance'):
            raise click.UsageError("--instance is required (or set in config/profile)")

        # Use merged values
        final_repository = merged['repository']
        final_instance = merged['instance']
        final_port = merged['port']
        final_strategy = merged['strategy']
        final_environment = merged['environment']
        final_health_path = health_path or "/health"

        mode_label = "[yellow]DRY-RUN MODE[/yellow]" if dry_run else ""
        console.print(Panel.fit(
            f"[bold cyan]DEPLOY Starting Deployment[/bold cyan] {mode_label}\n\n"
            f"Repository: [yellow]{final_repository}[/yellow]\n"
            f"Instance: [yellow]{final_instance}[/yellow]\n"
            f"Port: [yellow]{final_port}[/yellow]\n"
            f"Strategy: [yellow]{final_strategy}[/yellow]\n"
            f"Environment: [yellow]{final_environment}[/yellow]"
            + (f"\n[dim]Profile: {profile}[/dim]" if profile else ""),
            title="DeployMind",
            border_style="cyan"
        ))

        # Handle dry-run mode
        if dry_run:
            console.print("\n[yellow]DRY-RUN: Would execute deployment with the following steps:[/yellow]")
            console.print("  1. [cyan]Security Scan[/cyan]: Scan repository for vulnerabilities")
            console.print("  2. [cyan]Build Image[/cyan]: Build Docker image from repository")
            console.print("  3. [cyan]Deploy[/cyan]: Deploy to EC2 instance with health checks")
            console.print(f"\n[green]DRY-RUN: Deployment plan validated successfully![/green]")
            return

        # Load settings
        settings = Settings.load()

        # Create workflow
        workflow = FullDeploymentWorkflow(settings)

        # Create request
        request = FullDeploymentRequest(
            repository=final_repository,
            instance_id=final_instance,
            port=final_port,
            health_check_path=final_health_path,
            strategy=final_strategy,
            environment=final_environment
        )

        # Execute deployment with progress tracking
        # Note: Removed SpinnerColumn to avoid Unicode encoding issues on Windows
        # Windows cp1252 encoding can't handle Unicode spinner characters
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            # Phase 1: Security Scan
            task1 = progress.add_task("[cyan]>> SECURITY Security scanning...", total=None)

            # Phase 2: Build
            task2 = progress.add_task("[cyan]>> BUILD Building Docker image...", total=None)

            # Phase 3: Deploy
            task3 = progress.add_task("[cyan]>> DEPLOY Deploying to EC2...", total=None)

            # Execute workflow
            response = workflow.execute(request)

            progress.update(task1, completed=True)
            progress.update(task2, completed=True)
            progress.update(task3, completed=True)

        # Display results
        if response.success:
            console.print(Panel.fit(
                f"[bold green]SUCCESS Deployment Successful![/bold green]\n\n"
                f"Deployment ID: [yellow]{response.deployment_id}[/yellow]\n"
                f"Image Tag: [yellow]{response.image_tag}[/yellow]\n"
                f"Application URL: [yellow]{response.application_url}[/yellow]\n"
                f"Duration: [yellow]{response.duration_seconds:.2f}s[/yellow]",
                title="Success",
                border_style="green"
            ))
        else:
            console.print(Panel.fit(
                f"[bold red]FAILED Deployment Failed[/bold red]\n\n"
                f"Deployment ID: [yellow]{response.deployment_id}[/yellow]\n"
                f"Failed Phase: [red]{response.error_phase}[/red]\n"
                f"Error: [red]{response.error_message}[/red]\n"
                f"Rollback: [yellow]{'Yes' if response.rollback_performed else 'No'}[/yellow]",
                title="Failure",
                border_style="red"
            ))
            raise click.ClickException(response.error_message)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command(name="status")
@click.argument("deployment_id")
@click.pass_context
def status(ctx, deployment_id):
    """Get detailed status of a deployment by ID.

    Shows deployment information, security scan results, build status,
    and health check history.

    \b
    Example:
        deploymind status abc12345
        deploymind status --json abc12345
    """
    try:
        # Get deployment from database
        deployment = container.deployment_repo.get_by_id(deployment_id)

        if not deployment:
            console.print(f"[red]Deployment {deployment_id} not found[/red]")
            raise click.Abort()

        # Create status table
        table = Table(title=f"Deployment Status: {deployment_id}", box=box.ROUNDED)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="yellow")

        table.add_row("Status", f"[bold]{deployment.status}[/bold]")
        table.add_row("Repository", deployment.repository)
        table.add_row("Instance ID", deployment.instance_id)
        table.add_row("Image Tag", deployment.image_tag or "N/A")
        table.add_row("Strategy", deployment.strategy or "N/A")
        table.add_row("Created At", deployment.created_at.strftime("%Y-%m-%d %H:%M:%S"))

        if deployment.completed_at:
            table.add_row("Completed At", deployment.completed_at.strftime("%Y-%m-%d %H:%M:%S"))
            table.add_row("Duration", f"{deployment.duration_seconds:.2f}s" if deployment.duration_seconds else "N/A")

        console.print(table)

        # Get security scans
        scans = container.security_scan_repo.get_by_deployment(deployment_id)
        if scans:
            console.print("\n[bold cyan]Security Scans:[/bold cyan]")
            for scan in scans[:3]:  # Show last 3
                status_icon = "[green]PASS[/green]" if scan['passed'] else "[red]FAIL[/red]"
                console.print(f"  {status_icon} {scan['scanner']} - {scan['total_vulnerabilities']} vulnerabilities")

        # Get build results
        builds = container.build_result_repo.get_by_deployment(deployment_id)
        if builds:
            console.print("\n[bold cyan]Build Results:[/bold cyan]")
            for build in builds[:3]:  # Show last 3
                status_icon = "[green]SUCCESS[/green]" if build['success'] else "[red]FAILED[/red]"
                size_mb = build['image_size_bytes'] / (1024 * 1024) if build['image_size_bytes'] else 0
                console.print(f"  {status_icon} {build['image_tag']} - {size_mb:.1f} MB")

        # Get health checks
        checks = container.health_check_repo.get_by_deployment(deployment_id)
        if checks:
            console.print("\n[bold cyan]Health Checks:[/bold cyan]")
            healthy_count = sum(1 for c in checks if c['healthy'])
            console.print(f"  {healthy_count}/{len(checks)} checks passed")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command(name="list")
@click.option(
    "--limit", "-n",
    default=10,
    help="Number of deployments to show (default: 10)"
)
@click.option(
    "--repository", "-r",
    help="Filter by repository (owner/repo)"
)
@click.option(
    "--status", "-s",
    type=click.Choice(["pending", "security_scanning", "building", "deploying", "deployed", "failed"]),
    help="Filter by status"
)
@click.pass_context
def list(ctx, limit, repository, status):
    """List recent deployments with filtering options.

    Shows deployment history with status, duration, and metadata.
    Can filter by repository or status.

    \b
    Examples:
        deploymind list
        deploymind list --limit 20
        deploymind list -r user/app -n 50
        deploymind list --status deployed
    """
    try:
        # Get deployments from database
        if repository:
            deployments = container.deployment_repo.get_by_repository(repository, limit=limit)
        elif status:
            deployments = container.deployment_repo.get_by_status(status, limit=limit)
        else:
            deployments = container.deployment_repo.list_all(limit=limit)

        if not deployments:
            console.print("[yellow]No deployments found[/yellow]")
            return

        # Create table
        table = Table(title=f"Recent Deployments (showing {len(deployments)})", box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Repository", style="yellow")
        table.add_column("Instance", style="white")
        table.add_column("Status", style="green")
        table.add_column("Created", style="white")
        table.add_column("Duration", style="white")

        for deployment in deployments:
            # Status with colors
            status_map = {
                "deployed": "[green]DEPLOYED[/green]",
                "failed": "[red]FAILED[/red]",
                "deploying": "[yellow]DEPLOYING[/yellow]",
                "building": "[cyan]BUILDING[/cyan]",
                "security_scanning": "[blue]SCANNING[/blue]",
                "pending": "[white]PENDING[/white]"
            }
            status_display = status_map.get(deployment.status, deployment.status.upper())

            # Format times
            created = deployment.created_at.strftime("%m/%d %H:%M")
            duration = f"{deployment.duration_seconds:.1f}s" if deployment.duration_seconds else "-"

            table.add_row(
                deployment.id[:8],
                deployment.repository,
                deployment.instance_id[:12],
                status_display,
                created,
                duration
            )

        console.print(table)

        # Show summary statistics
        total = container.deployment_repo.count()
        console.print(f"\n[dim]Total deployments: {total}[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command(name="logs")
@click.argument("deployment_id")
@click.option(
    "--lines", "-n",
    default=50,
    help="Number of log lines to show (default: 50)"
)
@click.option(
    "--follow", "-f",
    is_flag=True,
    help="Follow log output (like tail -f)"
)
@click.pass_context
def logs(ctx, deployment_id, lines, follow):
    """Show deployment logs and build output.

    Displays build logs, deployment events, and error messages
    for a specific deployment.

    \b
    Examples:
        deploymind logs abc12345
        deploymind logs abc12345 --lines 100
        deploymind logs abc12345 --follow
    """
    console.print(f"[yellow]Logs for deployment {deployment_id}[/yellow]")
    console.print("[dim]Note: Full log streaming coming in next version[/dim]\n")

    try:
        # Get deployment
        deployment = container.deployment_repo.get_by_id(deployment_id)
        if not deployment:
            console.print(f"[red]Deployment {deployment_id} not found[/red]")
            raise click.Abort()

        # Show basic deployment info
        console.print(f"Repository: {deployment.repository}")
        console.print(f"Status: {deployment.status}")
        console.print(f"Created: {deployment.created_at}\n")

        # Show build logs if available
        builds = container.build_result_repo.get_by_deployment(deployment_id)
        if builds and builds[0].get('build_log'):
            console.print("[bold cyan]Build Log:[/bold cyan]")
            console.print(builds[0]['build_log'][:1000])  # Show first 1000 chars

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command(name="rollback")
@click.argument("deployment_id")
@click.option(
    "--confirm", "-y",
    is_flag=True,
    help="Skip confirmation prompt"
)
@click.pass_context
def rollback(ctx, deployment_id, confirm):
    """Rollback a deployment to previous version.

    Reverts the deployment to the last known good state.
    Requires confirmation unless --confirm flag is used.

    \b
    Examples:
        deploymind rollback abc12345
        deploymind rollback abc12345 -y
    """
    try:
        # Get deployment
        deployment = container.deployment_repo.get_by_id(deployment_id)
        if not deployment:
            console.print(f"[red]Deployment {deployment_id} not found[/red]")
            raise click.Abort()

        # Check if can rollback
        if not deployment.can_rollback():
            console.print(f"[red]Deployment {deployment_id} cannot be rolled back (status: {deployment.status})[/red]")
            raise click.Abort()

        # Confirm
        if not confirm:
            if not click.confirm(f"WARNING:  Are you sure you want to rollback deployment {deployment_id}?"):
                console.print("[yellow]Rollback cancelled[/yellow]")
                return

        console.print(Panel.fit(
            f"[bold yellow]ROLLBACK Rolling back deployment[/bold yellow]\n\n"
            f"Deployment ID: [yellow]{deployment_id}[/yellow]\n"
            f"Repository: [yellow]{deployment.repository}[/yellow]\n"
            f"Instance: [yellow]{deployment.instance_id}[/yellow]",
            title="Rollback",
            border_style="yellow"
        ))

        console.print("[yellow]Note: Rollback implementation coming in next version[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command(name="analytics")
@click.option(
    "--days", "-d",
    default=30,
    help="Number of days to analyze (default: 30)"
)
@click.option(
    "--repository", "-r",
    help="Filter by repository (owner/repo)"
)
@click.option(
    "--top", "-t",
    default=10,
    help="Number of top repositories to show (default: 10)"
)
@click.pass_context
def analytics(ctx, days, repository, top):
    """Show deployment analytics and performance metrics.

    Displays deployment statistics, success rates, duration metrics,
    security scan results, and top repositories by activity.

    \b
    Examples:
        deploymind analytics
        deploymind analytics --days 7
        deploymind analytics -r user/app -d 14
        deploymind analytics --top 20
    """
    try:
        analytics_service = DeploymentAnalytics()

        console.print(Panel.fit(
            f"[bold cyan]Deployment Analytics[/bold cyan]\n\n"
            f"Analysis Period: [yellow]Last {days} days[/yellow]"
            + (f"\nRepository: [yellow]{repository}[/yellow]" if repository else ""),
            title="Analytics",
            border_style="cyan"
        ))

        # Get overall metrics
        metrics = analytics_service.get_overall_metrics(days=days, repository=repository)

        # Overall Statistics
        console.print("\n[bold cyan]Overall Statistics:[/bold cyan]")
        stats_table = Table(box=box.ROUNDED)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="yellow")

        stats_table.add_row("Total Deployments", str(metrics.total_deployments))
        stats_table.add_row("Successful", f"[green]{metrics.successful_deployments}[/green]")
        stats_table.add_row("Failed", f"[red]{metrics.failed_deployments}[/red]")
        stats_table.add_row("Success Rate", f"{metrics.success_rate:.1f}%")

        if metrics.average_duration_seconds:
            stats_table.add_row("Average Duration", f"{metrics.average_duration_seconds:.1f}s")
            stats_table.add_row("Fastest Deployment", f"{metrics.fastest_deployment_seconds:.1f}s")
            stats_table.add_row("Slowest Deployment", f"{metrics.slowest_deployment_seconds:.1f}s")

        stats_table.add_row("Security Pass Rate", f"{metrics.security_scan_pass_rate:.1f}%")
        stats_table.add_row("Build Success Rate", f"{metrics.build_success_rate:.1f}%")

        console.print(stats_table)

        # Top Repositories
        if not repository:
            console.print(f"\n[bold cyan]Top {top} Repositories:[/bold cyan]")
            top_repos = analytics_service.get_top_repositories(limit=top)

            if top_repos:
                repo_table = Table(box=box.ROUNDED)
                repo_table.add_column("Repository", style="cyan")
                repo_table.add_column("Deployments", style="yellow")
                repo_table.add_column("Success Rate", style="green")
                repo_table.add_column("Avg Duration", style="white")

                for repo_stats in top_repos:
                    avg_dur = f"{repo_stats.average_duration_seconds:.1f}s" if repo_stats.average_duration_seconds else "N/A"
                    repo_table.add_row(
                        repo_stats.repository[:40],  # Truncate long names
                        str(repo_stats.total_deployments),
                        f"{repo_stats.success_rate:.1f}%",
                        avg_dur
                    )

                console.print(repo_table)
            else:
                console.print("[dim]No deployment data available[/dim]")

        # Failure Analysis
        if metrics.failed_deployments > 0:
            console.print("\n[bold cyan]Failure Analysis:[/bold cyan]")
            failure_analysis = analytics_service.get_failure_analysis(days=days)

            if failure_analysis["total_failures"] > 0:
                console.print(f"Total Failures: [red]{failure_analysis['total_failures']}[/red]")

                if failure_analysis["failure_by_repository"]:
                    console.print("\n[dim]Failures by Repository:[/dim]")
                    for repo, count in sorted(
                        failure_analysis["failure_by_repository"].items(),
                        key=lambda x: x[1],
                        reverse=True
                    )[:5]:
                        console.print(f"  {repo}: [red]{count}[/red]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


def main():
    """Main entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
