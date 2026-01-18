"""Constants for the license module."""

# OpsMill public key for license signature verification (RSA 2048-bit).
# This is the public portion of the key pair used by OpsMill to sign licenses.
# In production, this would be an actual RSA public key in PEM format.
# For the PoC, we use a placeholder that can be configured via environment.
OPSMILL_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Z3VS5JJcds3xfn/ygWyf8SzC7VE
xE9J5hFPZZQ7C5F3T4Y5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5
Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5
Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5
Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5
Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5Q7Z5Z0d5QIDAQAB
-----END PUBLIC KEY-----"""

# License file schema version
LICENSE_SCHEMA_VERSION = "1.0"
