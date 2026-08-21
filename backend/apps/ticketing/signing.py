from django.core import signing

# The salt isolates this signing use from any other the app may add later
# (e.g. password reset) — same SECRET_KEY, different namespaces.
SALT = "ticket-qr"


def sign_ticket_code(public_code: str) -> str:
    """Payload that goes in the QR. Only the backend, with SECRET_KEY, can
    produce a value that passes verification — that's what makes the QR
    unforgeable."""
    return signing.dumps(public_code, salt=SALT)


def unsign_ticket_code(token: str) -> str | None:
    """Returns the public_code if the signature is valid, else None (never raises)."""
    try:
        return signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None
