from dotenv import load_dotenv
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from base64 import b64encode
import json  # Ensure data is in JSON format

# Load environment variables from .env file
load_dotenv()
SECRET_KEY_DATA = os.getenv("SECRET_KEY_DATA").encode()  # Ensure this is bytes
BLOCK_SIZE = 16  # AES block size (16 bytes)

def encrypt_any_data(data: dict) -> str:
    # Convert dictionary to JSON string
    data_str = json.dumps(data)  # Use json.dumps for proper formatting
    
    # Ensure the key length is appropriate for AES (16, 24, or 32 bytes)
    key = SECRET_KEY_DATA.ljust(BLOCK_SIZE, b'\0')[:BLOCK_SIZE]  # Adjust key length

    # Create AES cipher
    cipher = AES.new(key, AES.MODE_CBC)
    
    # Encrypt data
    ct_bytes = cipher.encrypt(pad(data_str.encode(), BLOCK_SIZE))
    
    # Encode IV and ciphertext to Base64
    iv = b64encode(cipher.iv).decode('utf-8')
    ct = b64encode(ct_bytes).decode('utf-8')
    
    # Return combined IV and ciphertext
    return iv + ":" + ct

# Example Usage
data = {
    "user": {
        "id": 12345,
        "name": "John Doe",
        "email": "john.doe@example.com",
        "roles": ["admin", "user"],
        "preferences": {
            "theme": "dark",
            "notifications": True,
            "language": "en"
        }
    },
    "session": {
        "token": "abcdef1234567890",
        "expires_in": 3600,
        "refresh_token": "refresh_token_123456"
    },
    "items": [
        {
            "id": 1,
            "name": "Item 1",
            "quantity": 10,
            "price": 99.99
        },
        {
            "id": 2,
            "name": "Item 2",
            "quantity": 5,
            "price": 49.99
        }
    ],
    "metadata": {
        "timestamp": "2024-09-13T10:00:00Z",
        "request_id": "request_id_123456"
    }
}

encrypted = encrypt_any_data(data)
print("Encrypted:", encrypted)
