import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .database import Database
from .generator import generate_flashcard
from .populate_data import populate_db
from .__version__ import __version__, __app_name__, __description__

app = typer.Typer(
    name=__app_name__,
    help=__description__,
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()


def get_database_path() -> str:
    return "flashcards.db"


def version_callback(value: bool):
    if value:
        console.print(f"[bold cyan]{__app_name__}[/bold cyan] version [green]{__version__}[/green]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
):
    """
    Worldbuilding Flashcard Generator

    Generate random creative prompts for worldbuilding by combining
    categories like terrain, era, and character types.
    """
    pass


@app.command()
def generate(
    db_path: Optional[str] = typer.Option(None, "--db", help="Custom database path"),
):
    """
    Generate random flashcard

    Example:
        ca-flash-cards generate
    """
    with Database(db_path or get_database_path()) as db:
        if db.is_empty():
            console.print("[red]✗[/red] Database not initialized. Run 'ca-flash-cards init' first.")
            raise typer.Exit(code=1)

        flashcard = generate_flashcard(db)
        if flashcard:
            console.print(f"[bold cyan]>[/bold cyan] {flashcard}")
        else:
            console.print("[red]✗[/red] No categories found.")
            raise typer.Exit(code=1)


@app.command("add-category")
def add_category(
    name: str = typer.Argument(..., help="Category name to add"),
    db_path: Optional[str] = typer.Option(None, "--db", help="Custom database path"),
):
    """
    Add a new category

    Example:
        flashcards add-category weather
    """
    with Database(db_path or get_database_path()) as db:
        category_id = db.get_or_create_category(name)
        console.print(f"[green]✓[/green] Category '[cyan]{name}[/cyan]' created (ID: {category_id})")


@app.command("add-option")
def add_option(
    category: str = typer.Argument(..., help="Category name"),
    value: str = typer.Argument(..., help="Option value (use quotes for spaces)"),
    db_path: Optional[str] = typer.Option(None, "--db", help="Custom database path"),
):
    """
    Add an option to a category

    Examples:
        ca-flash-cards add-option terrain tundra
        ca-flash-cards add-option era "solar punk"
    """
    with Database(db_path or get_database_path()) as db:
        try:
            if db.add_option(category, value):
                console.print(f"[green]✓[/green] Added '[yellow]{value}[/yellow]' to category '[cyan]{category}[/cyan]'")
            else:
                console.print(f"[red]✗[/red] Option '[yellow]{value}[/yellow]' already exists in category '[cyan]{category}[/cyan]'")
                raise typer.Exit(code=1)
        except ValueError as e:
            console.print(f"[red]✗[/red] {e}")
            raise typer.Exit(code=1)


@app.command("list-categories")
def list_categories(
    db_path: Optional[str] = typer.Option(None, "--db", help="Custom database path"),
):
    """
    List all categories

    Example:
        flashcards list-categories
    """
    with Database(db_path or get_database_path()) as db:
        categories = db.get_all_categories()

        if categories:
            table = Table(title="Categories", show_header=True, header_style="bold magenta")
            table.add_column("#", style="dim", width=6)
            table.add_column("Name", style="cyan")
            table.add_column("Options", justify="right", style="green")

            for idx, cat in enumerate(categories, 1):
                option_count = len(db.get_options_by_category(cat))
                table.add_row(str(idx), cat, str(option_count))

            console.print(table)
        else:
            console.print("[yellow]No categories found.[/yellow]")


@app.command("list-options")
def list_options(
    category: str = typer.Argument(..., help="Category name"),
    db_path: Optional[str] = typer.Option(None, "--db", help="Custom database path"),
):
    """
    List options in a category

    Example:
        flashcards list-options terrain
    """
    with Database(db_path or get_database_path()) as db:
        options = db.get_options_by_category(category)

        if options:
            table = Table(title=f"Options in '{category}'", show_header=True, header_style="bold magenta")
            table.add_column("#", style="dim", width=6)
            table.add_column("Value", style="yellow")

            for idx, opt in enumerate(options, 1):
                table.add_row(str(idx), opt)

            console.print(table)
        else:
            console.print(f"[yellow]No options found in category '[cyan]{category}[/cyan]'[/yellow]")


@app.command()
def init(
    data_file: Optional[str] = typer.Option(None, "--data-file", help="YAML file path to load data from"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reinitialization"),
    db_path: Optional[str] = typer.Option(None, "--db", help="Custom database path"),
):
    """
    Initialize database (empty or from YAML)

    Examples:
        ca-flash-cards init                              # Empty database
        ca-flash-cards init --data-file my_data.yaml     # Load from YAML
    """
    with Database(db_path or get_database_path()) as db:
        if not force and not db.is_empty():
            if not typer.confirm("Database already has data. Reinitialize?"):
                console.print("[yellow]Cancelled.[/yellow]")
                raise typer.Exit()

        if data_file:
            from .populate_data import load_initial_data
            try:
                data = load_initial_data(data_file)
                count = populate_db(db, data)
                num_categories = len(db.get_all_categories())
                console.print(f"[green]✓[/green] Database initialized with {count} options across {num_categories} categories")
            except FileNotFoundError:
                console.print(f"[red]✗[/red] Data file not found: {data_file}")
                raise typer.Exit(code=1)
        else:
            console.print(f"[green]✓[/green] Database initialized (empty)")


@app.command()
def stats(
    db_path: Optional[str] = typer.Option(None, "--db", help="Custom database path"),
):
    """
    Show database statistics

    Example:
        flashcards stats
    """
    with Database(db_path or get_database_path()) as db:
        categories = db.get_all_categories()

        table = Table(title="Database Statistics", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        total_options = sum(len(db.get_options_by_category(cat)) for cat in categories)

        table.add_row("Total Categories", str(len(categories)))
        table.add_row("Total Options", str(total_options))
        table.add_row("Avg Options/Category", f"{total_options / len(categories):.1f}" if categories else "0")

        console.print(table)


def cli_main():
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled.[/yellow]")
        sys.exit(130)
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
