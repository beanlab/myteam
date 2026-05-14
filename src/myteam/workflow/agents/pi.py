EXEC = 'pi'
EXIT_SEQUENCE = b'\quit'
PTY_RIGHT_ARROW = b"\x1b[C"

def encode_input(text: str) -> bytes:
    payload = text.rstrip("\r\n")
    return payload.encode("utf-8") + PTY_RIGHT_ARROW + b"\r"

def get_session_id(nonce: str) -> str:
    """Retrieves the current session ID"""
    ...