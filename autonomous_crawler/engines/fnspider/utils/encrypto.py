import hashlib


def hash_md5(value):
    """
    将数据加密为 md5 值，方便存储和查询
    """
    m = hashlib.md5()
    m.update(value.encode())
    return m.hexdigest()
