"""
PlayStation PKG / PFS Cryptographic Functions
Cross-platform implementation of PS4 and PS3 crypto operations.
"""
import hashlib
import hmac
import struct
from typing import Tuple, Optional

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from . import keys


def sha256(data: bytes) -> bytes:
    """Compute SHA-256 hash."""
    return hashlib.sha256(data).digest()


def hmac_sha256(key: bytes, data: bytes) -> bytes:
    """Compute HMAC-SHA256."""
    return hmac.new(key, data, hashlib.sha256).digest()


def xor_bytes(a: bytes, b: bytes) -> bytes:
    """XOR two byte arrays of equal length."""
    return bytes(x ^ y for x, y in zip(a, b))


def compute_keys(content_id: str, passcode: str, index: int) -> bytes:
    """
    Computes derived keys from content_id, passcode, and key index.
    Matches LibOrbisPkg Crypto.ComputeKeys.
    """
    if len(content_id) != 36:
        raise ValueError(f"Content ID must be 36 characters long (got {len(content_id)})")
    if len(passcode) != 32:
        raise ValueError(f"Passcode must be 32 characters long (got {len(passcode)})")

    idx_bytes = struct.pack('>I', index)
    cid_padded = content_id.encode('ascii').ljust(48, b'\x00')
    pass_bytes = passcode.encode('ascii')

    data = sha256(idx_bytes) + sha256(cid_padded) + pass_bytes
    return sha256(data)


def rsa2048_decrypt_pkcs1(ciphertext: bytes, keyset: keys.RSAKeyset) -> Optional[bytes]:
    """
    Decrypts 256-byte ciphertext using RSA-2048 with PKCS#1 v1.5 padding.
    """
    try:
        p = int.from_bytes(keyset.prime1, 'big')
        q = int.from_bytes(keyset.prime2, 'big')
        d = int.from_bytes(keyset.private_exponent, 'big')
        dmp1 = int.from_bytes(keyset.exponent1, 'big')
        dmq1 = int.from_bytes(keyset.exponent2, 'big')
        iqmp = int.from_bytes(keyset.coefficient, 'big')
        e = int.from_bytes(keyset.public_exponent, 'big')
        n = int.from_bytes(keyset.modulus, 'big')

        priv_numbers = rsa.RSAPrivateNumbers(p, q, d, dmp1, dmq1, iqmp, rsa.RSAPublicNumbers(e, n))
        priv_key = priv_numbers.private_key()
        return priv_key.decrypt(ciphertext, padding.PKCS1v15())
    except Exception:
        # Fallback raw / manual decrypt attempt
        try:
            d = int.from_bytes(keyset.private_exponent, 'big')
            n = int.from_bytes(keyset.modulus, 'big')
            c = int.from_bytes(ciphertext, 'big')
            m = pow(c, d, n)
            raw = m.to_bytes(256, 'big')
            # Check PKCS#1 v1.5 padding: 00 02 [non-zero padding] 00 [data]
            if raw.startswith(b'\x00\x02'):
                sep = raw.find(b'\x00', 2)
                if sep != -1:
                    return raw[sep + 1:]
            return raw
        except Exception:
            return None


def rsa2048_encrypt_pkcs1(plaintext: bytes, modulus: bytes, public_exponent: bytes = b'\x00\x01\x00\x01') -> bytes:
    """
    Encrypts data using RSA-2048 with PKCS#1 v1.5 padding.
    """
    n = int.from_bytes(modulus, 'big')
    e = int.from_bytes(public_exponent, 'big')
    pub_numbers = rsa.RSAPublicNumbers(e, n)
    pub_key = pub_numbers.public_key()
    return pub_key.encrypt(plaintext, padding.PKCS1v15())


def aes_cbc_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    """Decrypt AES-128-CBC with no padding."""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    dec = cipher.decryptor()
    return dec.update(ciphertext) + dec.finalize()


def aes_cbc_encrypt(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    """Encrypt AES-128-CBC with no padding."""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    enc = cipher.encryptor()
    return enc.update(plaintext) + enc.finalize()


def pfs_gen_crypto_key(ekpfs: bytes, seed: bytes, index: int) -> bytes:
    """
    Assigning key generator based on EKPFS and PFS header seed.
    d = index (4 bytes LE) + seed
    return HMAC-SHA256(ekpfs, d)
    """
    d = struct.pack('<I', index) + seed
    return hmac_sha256(ekpfs, d)


def pfs_gen_enc_key(ekpfs: bytes, seed: bytes, new_crypt: bool = False) -> Tuple[bytes, bytes]:
    """
    Generates (tweak_key, data_key) for AES-XTS.
    """
    base_key = hmac_sha256(ekpfs, seed) if new_crypt else ekpfs
    enc_key = pfs_gen_crypto_key(base_key, seed, 1)
    tweak_key = enc_key[0:16]
    data_key = enc_key[16:32]
    return tweak_key, data_key


def decrypt_entry(entry_bytes: bytes, meta_bytes: bytes, key_seed: bytes) -> bytes:
    """
    Decrypts a PKG entry using its meta entry bytes and key seed.
    iv_key = SHA256(meta_bytes + key_seed)
    iv = iv_key[:16]
    key = iv_key[16:32]
    """
    iv_key = sha256(meta_bytes + key_seed)
    iv = iv_key[:16]
    key = iv_key[16:32]
    return aes_cbc_decrypt(entry_bytes, key, iv)


def encrypt_entry(entry_bytes: bytes, meta_bytes: bytes, key_seed: bytes) -> bytes:
    """
    Encrypts a PKG entry using its meta entry bytes and key seed.
    """
    iv_key = sha256(meta_bytes + key_seed)
    iv = iv_key[:16]
    key = iv_key[16:32]
    return aes_cbc_encrypt(entry_bytes, key, iv)


def decrypt_pfs_sector_xts(sector: bytes, sector_num: int, data_key: bytes, tweak_key: bytes) -> bytes:
    """
    Decrypts an AES-XTS sector (typically 4096 bytes).
    Tweak = sector_num (8 bytes LE) + 8 zero bytes.
    Key in cryptography modes.XTS is data_key + tweak_key (32 bytes).
    """
    tweak = struct.pack('<Q', sector_num) + b'\x00' * 8
    xts_key = data_key + tweak_key
    cipher = Cipher(algorithms.AES(xts_key), modes.XTS(tweak))
    decryptor = cipher.decryptor()
    return decryptor.update(sector) + decryptor.finalize()


def create_keystone(passcode: str) -> bytes:
    """Creates a keystone file for fake PKG."""
    keystone_header = bytes.fromhex("6b657973746f6e65020001000000000000000000000000000000000000000000")
    fingerprint = hmac_sha256(keys.keystone_hmac_key, passcode.encode('ascii'))
    final = hmac_sha256(keys.keystone_mac_data, keystone_header + fingerprint)
    return keystone_header + fingerprint + final
