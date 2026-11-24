"""对称加解密：用于安全存储 Git 凭据（Token / 私钥 / 密码）。

实现基于标准库的 Fernet 风格方案：PBKDF2-HMAC-SHA256 派生密钥，
AES 不可用时使用 HMAC-SHA256 的 CTR 模式流加密 + HMAC 校验（encrypt-then-MAC）。
密钥来自环境变量 CREDENTIAL_SECRET，未配置时回退到 jwt_secret。
凭据明文永不写库、不进日志；API 只返回是否已配置的状态。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

from .config import settings


def _key() -> bytes:
    secret = os.getenv("CREDENTIAL_SECRET") or settings.jwt_secret
    return hashlib.pbkdf2_hmac(
        "sha256", secret.encode("utf-8"), b"gma-credential-v1", 120_000, dklen=32
    )


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest())
        counter += 1
    return bytes(out[:length])


def encrypt(plaintext: str) -> str:
    """加密明文，返回可直接入库的字符串。空串原样返回。"""
    if not plaintext:
        return ""
    key = _key()
    nonce = os.urandom(16)
    data = plaintext.encode("utf-8")
    cipher = bytes(a ^ b for a, b in zip(data, _keystream(key, nonce, len(data))))
    tag = hmac.new(key, nonce + cipher, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(nonce + tag + cipher).decode("ascii")


def decrypt(token: str) -> str:
    """解密；任何篡改或密钥不匹配都返回空串，绝不抛异常到业务层。"""
    if not token:
        return ""
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        nonce, tag, cipher = raw[:16], raw[16:32], raw[32:]
        if len(nonce) != 16 or len(tag) != 16:
            return ""
        key = _key()
        expected = hmac.new(key, nonce + cipher, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(tag, expected):
            return ""
        plain = bytes(a ^ b for a, b in zip(cipher, _keystream(key, nonce, len(cipher))))
        return plain.decode("utf-8")
    except Exception:
        return ""
