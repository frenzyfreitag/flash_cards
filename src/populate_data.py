import yaml
from .database import Database


def load_initial_data(yaml_path: str) -> dict:
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)


def populate_db(db: Database, data: dict) -> int:
    added_count = 0
    for category_name, options in data.items():
        db.get_or_create_category(category_name)
        for option_value in options:
            if db.add_option(category_name, option_value):
                added_count += 1
    return added_count
