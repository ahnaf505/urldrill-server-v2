import hashlib
from db import *

def integrity_check(cookies) -> bool:
    required_keys = ["keyone", "keytwo", "keythree", "keyhash"]
    if all(key in cookies for key in required_keys):
        keyone = cookies.get("keyone").encode()
        keytwo = cookies.get("keytwo").encode()
        keythree = cookies.get("keythree").encode()
        if cookies.get("keyhash") == hashlib.sha256(keyone+keytwo+keythree).hexdigest():
            return True
        else:
            return False
    else:
        False

async def check_session(key1, key2, key3):
    if await is_logged_in_logic((key1, key2, key3)):
        return True
    else:
        return False

def hash(text):
    return hashlib.sha256(text.encode()).hexdigest()