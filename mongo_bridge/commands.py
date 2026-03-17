import click
import frappe


@click.command("mongo-stats")
@click.option("--site", required=True, help="Site name")
def get_stats(site):
    """Real-time MongoDB Health Check"""
    frappe.init(site=site)
    frappe.connect()
    try:
        from mongo_bridge.utils import get_mg
        mg = get_mg()
        status = mg.get_status()
        click.secho(f"\n--- MongoDB Monitor [{site}] ---", fg="cyan", bold=True)
        click.echo(f"Uptime:      {status['uptime']}s")
        click.echo(f"Version:     {status['version']}")
        click.echo(f"Connections: {status['connections']['current']} active")
        mem = status['mem']['resident']
        color = "green" if mem < 512 else "yellow"
        click.secho(f"Memory:      {mem}MB Resident", fg=color)
    except Exception as e:
        click.secho(f"Error: {str(e)}", fg="red")
    finally:
        frappe.destroy()


commands = [get_stats]