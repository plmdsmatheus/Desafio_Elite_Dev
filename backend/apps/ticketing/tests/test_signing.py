from apps.ticketing.signing import sign_ticket_code, unsign_ticket_code


class TestSigning:
    def test_roundtrip(self):
        token = sign_ticket_code("ABC123XYZ0")
        assert unsign_ticket_code(token) == "ABC123XYZ0"

    def test_tampered_token_is_rejected(self):
        token = sign_ticket_code("ABC123XYZ0")
        assert unsign_ticket_code(token + "tampered") is None

    def test_garbage_input_is_rejected_not_raised(self):
        assert unsign_ticket_code("not-a-signed-token-at-all") is None

    def test_different_codes_produce_different_tokens(self):
        assert sign_ticket_code("CODE0000A") != sign_ticket_code("CODE0000B")
