from setting import aesKey
from Crypto.Cipher import AES
def _pad(s): return s + (AES.block_size - len(s) % AES.block_size) * chr(AES.block_size - len(s) % AES.block_size)
def _cipher():
    keyHex = aesKey
    key=bytes.fromhex(keyHex)
    return AES.new(key=key, mode=AES.MODE_ECB)
def encrypt_token(data):
    """
    加密数据，将原始字符串加密为hex字符串
    :param data: 原始字符串
    :return: 加密后hex
    """
    return _cipher().encrypt(_pad(data)).hex()
def decrypt_token(data):
    """
    解密数据，将hex字符转化为原始字符串
    :param data: hex字符串
    :return:加密文档字符串
    """
    return str(_cipher().decrypt(bytes.fromhex(data)),"utf8")
if __name__ == '__main__':
    # print(bool("False"))
    print('Python encrypt: ' +encrypt_token('123456'))
    print('Python decrypt: ' +decrypt_token('723e5d24edbfcd6f85173e9b4a80d1f1'))