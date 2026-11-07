class AppError(Exception):
    def __init__(self, message, status=400, error="BAD_REQUEST"):
        super().__init__(message)
        self.status, self.error = status, error


class AuthError(AppError):
    pass
