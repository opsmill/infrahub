class MigrationFailureError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__()
        self.errors = errors
