import random

from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

Base = declarative_base()


class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    options = relationship("Option", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"


class Option(Base):
    __tablename__ = 'options'

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    value = Column(String, nullable=False)
    repeats_remaining = Column(Integer, default=1, nullable=False)
    category = relationship("Category", back_populates="options")

    def __repr__(self):
        return f"<Option(id={self.id}, value='{self.value}', category_id={self.category_id})>"

    __table_args__ = (
        {'sqlite_autoincrement': True},
    )


class Database:
    def __init__(self, db_path: str = "flashcards.db"):
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Base.metadata.create_all(self.engine)
        session_local = sessionmaker(bind=self.engine)
        self.session: Session = session_local()

    def _validate_non_empty(self, value: str, field_name: str) -> None:
        """Validate that a string value is not empty."""
        if not value or not value.strip():
            raise ValueError(f"{field_name} cannot be empty")

    def _get_category_by_name(self, name: str) -> Category:
        """Get category by name, raise if not found."""
        category = self.session.query(Category).filter_by(name=name).first()
        if not category:
            raise ValueError(f"Category '{name}' does not exist")
        return category

    def _validate_repeats(self, repeats: int) -> None:
        """Validate repeats value."""
        if repeats < 1:
            raise ValueError("Repeats must be at least 1")

    def _get_categories_by_names(self, category_names: list[str]) -> list[Category]:
        """Get categories by names, validate all exist."""
        categories = self.session.query(Category).filter(
            Category.name.in_(category_names)
        ).all()
        found_names = {cat.name for cat in categories}
        for cat_name in category_names:
            if cat_name not in found_names:
                raise ValueError(f"Category '{cat_name}' does not exist")
        return categories

    def get_or_create_category(self, name: str) -> int:
        self._validate_non_empty(name, "Category name")

        category = self.session.query(Category).filter_by(name=name).first()
        if category:
            return category.id

        category = Category(name=name)
        self.session.add(category)
        self.session.commit()
        return category.id

    def add_option(self, category_name: str, value: str, repeats: int = 1) -> bool:
        self._validate_non_empty(category_name, "Category name")
        self._validate_non_empty(value, "Option value")
        self._validate_repeats(repeats)

        category = self._get_category_by_name(category_name)

        existing = self.session.query(Option).filter_by(
            category_id=category.id,
            value=value
        ).first()

        if existing:
            return False

        try:
            option = Option(
                category_id=category.id,
                value=value,
                repeats_remaining=repeats
            )
            self.session.add(option)
            self.session.commit()
            return True
        except IntegrityError:
            self.session.rollback()
            return False

    def get_all_categories(self) -> list[str]:
        categories = self.session.query(Category.name).order_by(Category.name).all()
        return [cat.name for cat in categories]

    def is_empty(self) -> bool:
        return self.session.query(Category).count() == 0

    def get_random_option_per_category(
        self, category_names: list[str] | None = None
    ) -> dict[str, str]:
        if category_names:
            categories = self._get_categories_by_names(category_names)
        else:
            categories = self.session.query(Category).all()

        result = {}

        for category in categories:
            if not category.options:
                continue

            available = [opt for opt in category.options if opt.repeats_remaining > 0]

            if not available:
                raise ValueError(
                    f"Category '{category.name}' exhausted. "
                    f"Run: cards reset-reps --cat {category.name}"
                )

            selected = random.choice(available)
            selected.repeats_remaining -= 1
            result[category.name] = selected.value

        self.session.commit()
        return result

    def reset_repeats(self, category_names: list[str] | None = None) -> int:
        if category_names:
            categories = self._get_categories_by_names(category_names)
            option_ids = [opt.id for cat in categories for opt in cat.options]
            if not option_ids:
                return 0
            self.session.query(Option).filter(Option.id.in_(option_ids)).update(
                {Option.repeats_remaining: 1}, synchronize_session=False
            )
            count = len(option_ids)
        else:
            count = self.session.query(Option).update(
                {Option.repeats_remaining: 1}, synchronize_session=False
            )

        self.session.commit()
        return count

    def set_repeats(self, category_name: str, option_value: str, repeats: int) -> None:
        self._validate_non_empty(category_name, "Category name")
        self._validate_non_empty(option_value, "Option value")
        self._validate_repeats(repeats)

        category = self._get_category_by_name(category_name)

        option = self.session.query(Option).filter_by(
            category_id=category.id,
            value=option_value
        ).first()

        if not option:
            raise ValueError(f"Option '{option_value}' not found in category '{category_name}'")

        option.repeats_remaining = repeats
        self.session.commit()

    def _delete_stale_categories(
        self, existing_categories: dict, yaml_categories: set
    ) -> tuple[int, int]:
        """Delete categories not in YAML. Returns (categories_removed, options_removed)."""
        removed_categories = 0
        removed_options = 0

        for cat_name in existing_categories.keys() - yaml_categories:
            category = existing_categories[cat_name]
            removed_options += len(category.options)
            self.session.delete(category)
            removed_categories += 1

        return removed_categories, removed_options

    def _sync_category_options(
        self, category: Category, yaml_option_set: set
    ) -> tuple[int, int]:
        """Sync options for a category. Returns (options_added, options_removed)."""
        existing_options = {opt.value: opt for opt in category.options}
        added = 0
        removed = 0

        for opt_value in existing_options.keys() - yaml_option_set:
            self.session.delete(existing_options[opt_value])
            removed += 1

        for option_value in yaml_option_set - set(existing_options.keys()):
            option = Option(
                category_id=category.id,
                value=option_value,
                repeats_remaining=1
            )
            self.session.add(option)
            added += 1

        return added, removed

    def sync_from_data(self, data: dict) -> dict[str, int]:
        """Sync database to match data exactly. Returns counts of added/removed items."""
        counts = {
            "added_categories": 0,
            "removed_categories": 0,
            "added_options": 0,
            "removed_options": 0,
        }

        existing_categories = {cat.name: cat for cat in self.session.query(Category).all()}
        yaml_categories = set(data.keys())

        removed_cats, removed_opts = self._delete_stale_categories(
            existing_categories, yaml_categories
        )
        counts["removed_categories"] = removed_cats
        counts["removed_options"] = removed_opts

        self.session.flush()

        for category_name, yaml_options in data.items():
            yaml_option_set = set(yaml_options or [])

            if category_name in existing_categories:
                category = existing_categories[category_name]
            else:
                category = Category(name=category_name)
                self.session.add(category)
                self.session.flush()
                counts["added_categories"] += 1

            added, removed = self._sync_category_options(category, yaml_option_set)
            counts["added_options"] += added
            counts["removed_options"] += removed

        self.session.commit()
        return counts

    def close(self):
        if self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        self.close()
