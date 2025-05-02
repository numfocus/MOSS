"""
backend.services.base_service
-----------------------------
Provides a foundational class for service layer components within the application.
"""

import logging

class BaseService:
    """
    Base class for service layer components.

    Offers common structure and setup, including a standardized logger instance.
    Subclasses should implement specific business logic and typically receive
    dependencies (like repositories or other services) during initialization.
    """
    # Initialize a logger specific to the service instance, named after the module.
    logger = logging.getLogger(__name__)

    def __init__(self):
        """
        Initializes the BaseService instance.

        Subclasses can override this method to inject necessary dependencies.
        """
        self.logger.debug(f"{self.__class__.__name__} initialized.")
        # Example structure for subclasses requiring dependency injection:
        # def __init__(self, some_repo: SomeRepository, another_service: AnotherService):
        #     super().__init__()
        #     self.some_repo = some_repo
        #     self.another_service = another_service

    # Common utility methods or shared functionality for services
    # could be added here in the future if needed.