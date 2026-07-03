from .database import Database


def generate_flashcard(
    db: Database, category_names: list[str] | None = None
) -> str | None:
    results = db.get_random_option_per_category(category_names)
    if not results:
        return None
    return ", ".join(results.values())
