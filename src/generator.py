from typing import Optional
from .database import Database


def generate_flashcard(db: Database) -> Optional[str]:
    results = db.get_random_option_per_category()
    if not results:
        return None
    return ", ".join(results.values())
