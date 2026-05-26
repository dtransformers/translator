from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy declarative models.
    """
    pass


# Import all models here so Alembic/create_all can discover them
from app.brands.models import Brand  # noqa: F401, E402
from app.translations.models import Translation, ReusableUnit  # noqa: F401, E402
