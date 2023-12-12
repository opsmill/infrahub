class TransferError(Exception):
    ...


class FileAlreadyExistsError(TransferError):
    ...


class FileNotFoundError(TransferError):
    ...


class InvalidNamespaceError(TransferError):
    ...


class SchemaImportError(TransferError):
    ...
