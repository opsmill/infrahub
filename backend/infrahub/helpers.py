import bcrypt


def is_hashed_password(password: str) -> bool:
    """Tell if a password is (potentially) already hashed.

    There are no real ways to make sure a string is actually a hash. It's even more true when it comes to passwords as they can be strong even if
    it's unlikely. This functions is only an attempt at guessing if the password should go through a hash process or not.
    """
    try:
        bcrypt.checkpw(b"", password.encode())
        return True
    except ValueError:
        return False


def hash_password(password: str) -> str:
    """Hash a password for storage in the database."""
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode("UTF-8"), salt)
    return hashed_password.decode("UTF-8")
