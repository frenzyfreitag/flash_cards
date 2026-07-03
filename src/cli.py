import random
import sys

import typer
from rich.console import Console

from .__version__ import __app_name__, __description__, __version__
from .database import Database
from .generator import generate_flashcard
from .populate_data import load_initial_data, populate_db

app = typer.Typer(
    name=__app_name__,
    help=__description__,
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()
DB_PATH = "flashcards.db"


def version_callback(value: bool):
    if value:
        console.print(f"[bold cyan]{__app_name__}[/bold cyan] version [green]{__version__}[/green]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
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


@app.command("gen")
def generate(
    cat: str | None = typer.Option(None, "--cat", help="Comma-separated category names"),
    rand_cat: int | None = typer.Option(
        None, "--rand-cat", help="Number of random categories to select"
    ),
    db_path: str | None = typer.Option(None, "--db", help="Custom database path"),
):
    """
    Generate random flashcard

    Examples:
        cards gen
        cards gen --cat "terrain,era"
        cards gen --rand-cat 4
    """
    with Database(db_path or DB_PATH) as db:
        if db.is_empty():
            console.print("[red]✗[/red] Database not initialized. Run 'cards init' first.")
            raise typer.Exit(code=1)

        if cat and rand_cat:
            console.print("[red]✗[/red] Cannot use both --cat and --rand-cat")
            raise typer.Exit(code=1)

        try:
            if rand_cat is not None:
                if rand_cat < 1:
                    console.print("[red]✗[/red] --rand-cat must be at least 1")
                    raise typer.Exit(code=1)
                all_categories = db.get_all_categories()
                if rand_cat > len(all_categories):
                    console.print(
                        f"[red]✗[/red] Requested {rand_cat} categories "
                        f"but only {len(all_categories)} available"
                    )
                    raise typer.Exit(code=1)
                category_list = random.sample(all_categories, rand_cat)
            else:
                category_list = [c.strip() for c in cat.split(",")] if cat else None

            flashcard = generate_flashcard(db, category_list)
            if flashcard:
                console.print(f"[bold cyan]>[/bold cyan] {flashcard}")
            else:
                console.print("[red]✗[/red] No categories found.")
                raise typer.Exit(code=1)
        except ValueError as e:
            console.print(f"[red]✗[/red] {e}")
            raise typer.Exit(code=1) from e


@app.command()
def init(
    data_file: str | None = typer.Option(
        None, "--data-file", help="YAML file path to load data from"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Force reinitialization"),
    db_path: str | None = typer.Option(None, "--db", help="Custom database path"),
):
    """
    Initialize database (empty or from YAML)

    Examples:
        cards init                              # Empty database
        cards init --data-file my_data.yaml     # Load from YAML
    """
    with Database(db_path or DB_PATH) as db:
        if not force and not db.is_empty():
            if not typer.confirm("Database already has data. Reinitialize?"):
                console.print("[yellow]Cancelled.[/yellow]")
                raise typer.Exit()

        if data_file:
            try:
                data = load_initial_data(data_file)
                count = populate_db(db, data)
                num_categories = len(db.get_all_categories())
                console.print(
                    f"[green]✓[/green] Database initialized with {count} options "
                    f"across {num_categories} categories"
                )
            except FileNotFoundError as e:
                console.print(f"[red]✗[/red] Data file not found: {data_file}")
                raise typer.Exit(code=1) from e
        else:
            console.print("[green]✓[/green] Database initialized (empty)")


@app.command()
def update(
    data_file: str = typer.Option(..., "--data-file", help="YAML file path to update from"),
    db_path: str | None = typer.Option(None, "--db", help="Custom database path"),
):
    """
    Update database from YAML (adds new categories/options, preserves existing)

    Example:
        cards update --data-file my_data.yaml
    """
    with Database(db_path or DB_PATH) as db:
        if db.is_empty():
            console.print("[red]✗[/red] Database not initialized. Run 'cards init' first.")
            raise typer.Exit(code=1)

        try:
            data = load_initial_data(data_file)
            added_categories = 0
            added_options = 0

            existing_categories = db.get_all_categories()

            for category_name, options in data.items():
                if category_name not in existing_categories:
                    db.get_or_create_category(category_name)
                    added_categories += 1

                if options:
                    for option_value in options:
                        try:
                            if db.add_option(category_name, option_value):
                                added_options += 1
                        except ValueError:
                            pass

            if added_categories == 0 and added_options == 0:
                console.print("[yellow]No new categories or options to add.[/yellow]")
            else:
                console.print(
                    f"[green]✓[/green] Updated database: "
                    f"{added_categories} new categories, {added_options} new options"
                )

        except FileNotFoundError as e:
            console.print(f"[red]✗[/red] Data file not found: {data_file}")
            raise typer.Exit(code=1) from e


@app.command("set-reps")
def set_repeats(
    repeats: int = typer.Argument(..., help="Repeats value (1 or higher)"),
    cat: str = typer.Option(..., "--cat", help="Category name"),
    option: str = typer.Option(..., "--opt", help="Option value"),
    db_path: str | None = typer.Option(None, "--db", help="Custom database path"),
):
    """
    Set repeats for a specific option

    Example:
        cards set-reps 7 --cat terrain --opt mountain
    """
    if repeats < 1:
        console.print("[red]✗[/red] Repeats must be 1 or higher")
        raise typer.Exit(code=1)

    with Database(db_path or DB_PATH) as db:
        try:
            db.set_repeats(cat, option, repeats)
            console.print(
                f"[green]✓[/green] Set '[yellow]{option}[/yellow]' in '[cyan]{cat}[/cyan]' "
                f"to repeats={repeats}"
            )
        except ValueError as e:
            console.print(f"[red]✗[/red] {e}")
            raise typer.Exit(code=1) from e


@app.command("reset-reps")
def reset_repeats(
    all_categories: bool = typer.Option(False, "--all", help="Reset all categories to 1"),
    cat: str | None = typer.Option(
        None, "--cat", help="Comma-separated category names to reset to 1"
    ),
    db_path: str | None = typer.Option(None, "--db", help="Custom database path"),
):
    """
    Reset repeats for categories (sets all to 1)

    Examples:
        cards reset-reps --all
        cards reset-reps --cat terrain
        cards reset-reps --cat "terrain,era"
    """
    if not all_categories and not cat:
        console.print("[red]✗[/red] Specify --all or --cat <categories>")
        raise typer.Exit(code=1)

    with Database(db_path or DB_PATH) as db:
        try:
            if all_categories:
                count = db.reset_repeats(None)
                console.print(f"[green]✓[/green] Reset all categories to 1 ({count} options)")
            else:
                category_list = [c.strip() for c in cat.split(",")]
                count = db.reset_repeats(category_list)
                console.print(
                    f"[green]✓[/green] Reset {len(category_list)} category(ies) "
                    f"to 1 ({count} options)"
                )
        except ValueError as e:
            console.print(f"[red]✗[/red] {e}")
            raise typer.Exit(code=1) from e


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
