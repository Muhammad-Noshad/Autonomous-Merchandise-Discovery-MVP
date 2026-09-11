"""Small serialization helpers shared by MongoDB repositories."""

from typing import TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def to_document(model: BaseModel) -> dict:
    """Convert a validated model while preserving datetime values for MongoDB indexing."""

    return model.model_dump(mode="python")


def from_document(model_type: type[ModelT], document: dict | None) -> ModelT | None:
    """Rehydrate a MongoDB document into its typed application contract."""

    if document is None:
        return None
    return model_type.model_validate(document)

