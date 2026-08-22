from typing import Annotated
from bson import ObjectId
from pydantic import BeforeValidator, ConfigDict

# Custom validator that translates MongoDB ObjectIds into strings for JSON responses
PyObjectId = Annotated[str, BeforeValidator(lambda x: str(x) if isinstance(x, ObjectId) else x)]

class BaseSchemaModel:
    """
    Base configuration for Pydantic model schemas that maps MongoDB '_id' to client-facing 'id'.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
