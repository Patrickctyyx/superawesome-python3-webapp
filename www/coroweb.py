# -*- coding: utf-8 -*-

'web 框架'

__author__ = 'Patrick'

import functools# 高阶函数模块，提供常用的高阶函数，如wraps
import asyncio
import os
import inspect# 用来提供关于活动对象（live objects）的信息
import logging
from urllib import parse# 解析模块
from aiohttp import web
from apis import APIError

# 定义了一个装饰器
# 讲一个函数映射为一个url处理器
def get(path):
    '''Define decorator @get('/path')'''
    def decorator(func):
        # 该装饰器的作用是解决一些函数签名的问题
        # 比如若没有该装饰器,wrapper.__name__将为"wrapper"
        # 加了装饰器,wrapper.__name__就等于func.__name__
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        # 通过装饰器加上__method__属性，来表示http method
        wrapper.__method__ = 'GET'
        # 通过装饰器加上__route__属性，来表示path
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    '''Define decorator @post('/path')'''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method_ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

# 获取函数的值为空的命名关键字参数
def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        # 获取是命名关键字且未指定默认值的参数名
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

#获取命名关键字参数
def get_named_kw_args(fn):#kw一般指关键字参数
    args = []
    # 获取函数fn的全部参数
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        # KEYWORD_ONLY表示命名关键字参数
        # 下面的操作就是获得命名关键字参数名
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

# 判断函数fn是否有命名关键字参数
def has_named_kw_args(fn):
    params=inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

# 判断函数fn是否有关键字参数
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        # VAR_KEYWORD表示关键字参数，匹配**kw
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

# 检查fn是否含有请求关键字
def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name,param in params.items():
        if name == 'request':# 如果找到了以request为名字的参数，found为真
            found = True
            continue
        # VAR_POSITIONAL表示可选参数，匹配*args
        # 若已经找到request关键字，但其不是函数的最后一个参数就会报错
        # request参数必须是最后一个命名参数
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError("request parameter must be the last named parameter in function %s%s" % (fn.__name__, str(sig)))
    return found

# 定义RequestHandler类，封装url处理函数
# RequestHandler的目的是从url中分析所需要提取的参数，从request中获取必要的参数
# 调用url参数，将结果转化为web.Response
class RequestHandler(object):
    def __int__(self, app, fn):
        self._app = app# 网页应用
        self._func = fn# handler

        #一些上面定义的判断函数与获取函数
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    # 定义了__call__，则其实例可被视为函数
    @asyncio.coroutine
    def __call__(self, request):

        kw = None# 假设无关键字参数

        #存在关键字参数/命名关键字参数
        if self._has_named_kw_args or self._has_var_kw_arg or self._required_kw_args:
            # http method 为 post的处理
            if request.method == 'POST':
                # http method 为post但request 的content type为空返回丢失信息
                if not request.content_type:
                    return web.HTTPBadRequest("Missing Content-Type")
                ct = request.content_type.lower()# 获得content type字段
                # 以下为检查post请求的content type字段
                # application/json表示消息主题是序列化后的json字符串
                if ct.startswith("application/json"):
                    params = yield from request.json()# request.json()方法是读取request body，并以json格式解码
                    if not isinstance(params, dict):#解码得到的参数不是dict类型就返回提示类型
                        return web.HTTPBadRequest("JSON body must be object")
                    kw = params#post， content type字段指定的消息主体是json字符串，且解码得到的参数为dict类型的，将其赋给kw
                # 下面两种content type都表示消息主体是表单
                elif ct.startswith("application/x-www-form-urlencoded") or ct.startswith("multipart/form-data"):
                     # request.post方法从request body读取POST参数,即表单信息,并包装成字典赋给kw变量
                    params = yield from request.post()
                    kw = dict(**params)
                else:
                    #此处只处理以上三种post提交数据方式
                    return web.HTTPBadRequest("Unsupported Content-Type:%s" % request.content_type)

            # http method 为 get的处理
            if request.method == 'GET':
                # request.query_string表示url中的查询字符串
                # 比如"https://www.google.com/#newwindow=1&q=google",其中q=google就是query_string
                qs = request.query_string
                if qs:
                    kw = dict()# 原来为None的kw变为dict
                    for k,v in parse.parse_qs(qs,True).items():# 解析query_string，以dict的形式储存在kw中
                        kw[k] = v[0]

        if kw is None:# 如果上面这些以后kw还是空，即以上全部不匹配，则获取请求的抽象数学信息，并以dict的形式存入kw
            kw = dict(**request.match_info)
        else:
            # kw不为空且requesthandler只存在命名关键字，则只取命名关键字参数放入kw
            if not self._has_var_kw_arg and self._named_kw_args:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name]=kw[name]
                kw = copy
            # 检查request.match_info（抽象数学信息），如果其key又存在于kw中，发出重复参数警告
            for k,v in request.match_info.items():
                if k in kw:
                    logging.warning("Duplicate arg name in named arg and kw args:%s" % k)
                # 用math_info的值覆盖kw中的值
                kw[k] = v

        # 若存在request关键字，则添加
        if self._has_request_arg:
            kw['request'] = request
        # 若存在未指定值的命名关键字参数，且参数名未在kw中，返回丢失参数信息
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest()
        logging.info("Call with args:%s" % str(kw))
        # 以上过程即为从request中获得必要的参数

        # 以下为调用handler处理，并返回response
        try:
            r = yield from self._func(**kw)
            return r
        except APIError as e:
            return dict(error = e.error, data = e.data, message = e.message)

def add_static(app):
    # os.path.abspath(__file__), 返回当前脚本的绝对路径(包括文件名)
    # os.path.dirname(), 去掉文件名,返回目录路径
    # os.path.join(), 将分离的各部分组合成一个路径名
    # 因此以下操作就是将本文件同目录下的static目录(即www/static/)加入到应用的路由管理器中
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    app.router.add_static("/static/", path)
    logging.info("add static %s => %s" % ("/static/", path))

# 将处理函数注册到app上
# 处理将针对http method 和path进行
def add_route(app,fn):
    method = getattr(fn,"__method__", None)# 获取fn.__method__属性，若不存在就返回None
    path = getattr(fn,"__route__", None)
    # http method或path位置，将无法进行处理，因此报错
    if path is None or method is None:
        raise ValueError("@get or @post not defined in %s" % str(fn))
    # 将非协程或生成器的函数变成一个协程
    if not asyncio.coroutine(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info("add route %s %s =>%s(%s)" % (method,path, fn.__name__, '.'.join(inspect.signature(fn).parameters.keys())))
    # 注册request handler
    app.router.add_route(method, path, RequestHandler(app, fn))

# 自动注册所有请求处理函数
def add_routes(app, module_name):
    n = module_name.rfind('.')# 记录模块名中最后一个.的位置
    if n == (-1):# -1表示未找到，即module_name表示的模块直接导入
        # __import__()的作用同import语句,python官网说强烈不建议这么做
        # __import__(name, globals=None, locals=None, fromlist=(), level=0)
        # name -- 模块名
        # globals, locals -- determine how to interpret the name in package context
        # fromlist -- name表示的模块的子模块或对象名列表
        # level -- 绝对导入还是相对导入,默认值为0, 即使用绝对导入,正数值表示相对导入时,导入目录的父目录的层数
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n + 1:]
        # 先用__import__表达式导入模块和子模块
        # 再通过getarr（）方法获得子模块名
        mod = getattr(__import__(module_name[: n], globals(), locals(), [name]), name)

    # 遍历模块目录
    for attr in dir(mod):
        # 忽略以_开头的属性与方法,_xx或__xx(前导1/2个下划线)指示方法或属性为私有的,__xx__指示为特殊变量
        # 私有的,能引用(python并不存在真正私有),但不应引用;特殊的,可以直接应用,但一般有特殊用途
        if attr.startswith('_'):
            continue
        # 获得模块的属性或方法, 如datetime.datetime.now
        # 前一个datetime表示模块名,后一个表示子模块名,如果是以上述else方法导入的模块,就应为datetime.datetime形式
        fn = getattr(mod, attr)
        if callable(fn):
            # 获取fn的__method__属性与__route__属性获得http method与path信息
            # 此脚本开头的@get与@post装饰器就为fn加上了__method__与__route__
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)
