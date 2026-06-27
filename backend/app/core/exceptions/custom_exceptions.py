class BasePlatformException(Exception):
    """Base exception rule for all custom application errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class ResourceNotFoundException(BasePlatformException):
    """Raised when a requested resource (Customer, Interaction, etc.) does not exist."""
    pass

class ResourceAlreadyExistsException(BasePlatformException):
    """Raised when trying to create a resource that violates uniqueness rules."""
    pass

class BusinessRuleViolationException(BasePlatformException):
    """Raised when an operation violates a business state logic gate."""
    pass

class ExternalServiceException(BasePlatformException):
    """Raised when an external API handler (like the Gemini GenAI Client) fails."""
    pass