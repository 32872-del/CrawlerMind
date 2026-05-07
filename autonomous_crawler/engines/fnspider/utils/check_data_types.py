import inspect


def is_generator_function(func):
    """
    检测是否是yield方法或函数
    """
    return inspect.isgeneratorfunction(func)
