from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Optional, Any
from datetime import datetime
import random

Base = declarative_base()


class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    options = relationship("Option", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"


class Option(Base):
    __tablename__ = 'options'

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    value = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
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
        SessionLocal = sessionmaker(bind=self.engine)
        self.session: Session = SessionLocal()

    def get_or_create_category(self, name: str) -> int:
        category = self.session.query(Category).filter_by(name=name).first()
        if category:
            return category.id

        category = Category(name=name)
        self.session.add(category)
        self.session.commit()
        return category.id

    def add_option(self, category_name: str, value: str, repeats: int = 1) -> bool:
        category = self.session.query(Category).filter_by(name=category_name).first()
        if not category:
            raise ValueError(f"Category '{category_name}' does not exist")

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

    def get_all_categories(self) -> List[str]:
        categories = self.session.query(Category.name).order_by(Category.name).all()
        return [cat.name for cat in categories]

    def is_empty(self) -> bool:
        return self.session.query(Category).count() == 0

    def get_random_option_per_category(self) -> Dict[str, str]:
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

    def reset_repeats(self, category_names: Optional[List[str]] = None) -> int:
        if category_names:
            options = []
            for cat_name in category_names:
                category = self.session.query(Category).filter_by(name=cat_name).first()
                if not category:
                    raise ValueError(f"Category '{cat_name}' does not exist")
                options.extend(category.options)
        else:
            options = self.session.query(Option).all()

        for option in options:
            option.repeats_remaining = 1

        self.session.commit()
        return len(options)

    def set_repeats(self, category_name: str, option_value: str, repeats: int) -> None:
        category = self.session.query(Category).filter_by(name=category_name).first()
        if not category:
            raise ValueError(f"Category '{category_name}' does not exist")

        option = self.session.query(Option).filter_by(
            category_id=category.id,
            value=option_value
        ).first()

        if not option:
            raise ValueError(f"Option '{option_value}' not found in category '{category_name}'")

        option.repeats_remaining = repeats
        self.session.commit()

    def close(self):
        if self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
