class ServiceError(Exception):
    def __init__(self, message, *, details=None):
        super().__init__(message)
        self.details = details or {}


class NotFoundError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class InvalidReferenceError(ServiceError):
    pass


class AssociationError(ServiceError):
    pass


class ConfigurationError(ServiceError):
    pass


class InvalidCredentialsError(ServiceError):
    pass


class InactiveAccountError(ServiceError):
    pass


class InvalidDeviceCredentialsError(ServiceError):
    pass


class InactiveDeviceError(ServiceError):
    pass
