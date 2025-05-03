from django.conf import settings


def encrypt_string(plain_text: str) -> str:
    cipher_suite = settings.CIPHER_SUITE
    plaintext_bytes = plain_text.encode()
    encrypted_bytes = cipher_suite.encrypt(plaintext_bytes)
    encrypted_string = encrypted_bytes.decode()
    return encrypted_string


def decrypt_string(plain_text: str) -> str:
    cipher_suite = settings.CIPHER_SUITE
    encrypted_bytes = plain_text.encode()
    decrypted_bytes = cipher_suite.decrypt(encrypted_bytes)
    decrypted_string = decrypted_bytes.decode()
    return decrypted_string
