import bcrypt


def hash_password(password: str) -> str:
    """Hash a password for storage in the database."""
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode("UTF-8"), salt)
    return hashed_password.decode("UTF-8")
