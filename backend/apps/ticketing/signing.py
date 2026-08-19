from django.core import signing

# Salt isola esse uso do signing de qualquer outro que a aplicação venha a ter
# (ex.: reset de senha) — mesmo SECRET_KEY, namespaces diferentes.
SALT = "ticket-qr"


def sign_ticket_code(public_code: str) -> str:
    """Payload que vai no QR. Só o backend, com o SECRET_KEY, consegue gerar um
    valor que passe na verificação — é isso que torna o QR não forjável."""
    return signing.dumps(public_code, salt=SALT)


def unsign_ticket_code(token: str) -> str | None:
    """Retorna o public_code se a assinatura for válida, senão None (nunca levanta)."""
    try:
        return signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None
