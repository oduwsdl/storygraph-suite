from os.path import dirname, abspath

def cur_path():
    return dirname(abspath(__file__)) + '/'

__appversion__ = '0.0.0'
__installpath__ = cur_path()
