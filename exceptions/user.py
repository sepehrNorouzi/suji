class ReVerifyException(Exception):
    def __init__(self, message):
        super().__init__(message)

class EmailAlreadyTakenError(Exception):
    def __init__(self, message):
        super().__init__(message)
