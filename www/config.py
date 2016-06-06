# -*- coding: utf-8 -*-

'配置文件'

__author__ = 'Patrick'

import config_default

class Dict(dict):
    '''
    Simple dict but support access as x.y style.
    '''
    def __init__(self, names=(), values=(), **kw):
        super(Dict, self).__init__(**kw)
        # 建立key和value对应关系
        for k, v in zip(names, values):
            self[k] = v

    # 定义描述符，方便通过点标记法取值，比如a.b
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    # 定义描述符，方便通过点标记法设值，比如a.b=c
    def __setattr__(self, key, value):
        self[key] = value

# 将默认配置文件与自定义配置文件混合
def merge(defaults, override):
    r = {}# 创建一个空的字典,用于配置文件的融合,而不对任意配置文件做修改
    # 1) 从默认配置文件取key,优先判断该key是否在自定义配置文件中有定义
    # 2) 若有,则判断value是否是字典,
    # 3) 若是字典,重复步骤1
    # 4) 不是字典的,则优先从自定义配置文件中取值,相当于覆盖默认配置文件
    for k, v in defaults.items():
        if k in override:
            if isinstance(v, dict):
                r[k] = merge(v, override[k])
            else:
                r[k] = override[k]
        # 当前key在默认文件中有定义的，就从其中取值设值
        else:
            r[k] = v
    return r

# 将内建dict换成自定义Dict
def toDict(d):
    D = Dict()
    for k, v in d.items():
        # dict中某项value仍为dict的，如db，则将value的dict也转换成Dict
        D[k] = toDict(v) if isinstance(v, dict) else v
    return D

# 获得默认配置文件的配置信息
configs = config_default.configs

try:
    # 导入自定义配置文件，并将其与默认配置文件混合
    import config_override
    configs = merge(configs, config_override.configs)
except ImportError:
    pass

# 最后将混合好的dict转化为Dict，方便取值和设值
configs = toDict(configs)

