class TransferError(Exception):
    ...


class FileAlreadyExistsError(TransferError):
    ...


class TransferFileNotFoundError(TransferError):
    ...


class InvalidNamespaceError(TransferError):
    ...


class SchemaImportError(TransferError):
    ...
