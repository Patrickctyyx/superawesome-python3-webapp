# -*- coding: utf-8 -*-

'Web App骨架'

__author__ = 'Patrick'


import logging;logging.basicConfig(level = logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes, add_static

# 选择jinja2作为模板，初始化模板
def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    # 设置jinja2的Environment参数
    options = dict(
        autoescape = kw.get('autoescape', True), # 自动转义xml/html的特殊字符
        block_start_string = kw.get('block_start_string', '{%'), # 代码块开始标志
        block_end_string = kw.get('block_end_string', '%}'), # 代码块结束标志
        variable_start_string = kw.get('variable_start_string', '{{'), # 变量开始标志
        variable_end_string = kw.get('variable_end_string', '}}'), # 变量结束标志
        auto_reload = kw.get('auto_reload', True) # 每当对模板发起请求，加载器首先检查模板是否发生改变，若是，则重载模板
    )
    path=kw.get('path', None) # 若关键字参数制定了path，将其赋给path，否则置为None
    if path is None:
        # 如果路径不存在，则将当前目录下的templates设为jinja2的目录
        # os.path.abspath(__file__), 返回当前脚本的绝对路径(包括文件名)
        # os.path.dirname(), 去掉文件名,返回目录路径
        # os.path.join(), 将分离的各部分组合成一个路径名
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
    # 初始化jinja2华景，options参数之前已经设置过
    # 加载器负责从指定位置加载模板, 此处选择FileSystemLoader,顾名思义就是从文件系统加载模板,前面我们已经设置了path
    env = Environment(loader=FileSystemLoader(path), **options)
    # 设置过滤器
    # 先通过filters关键字参数获取过滤字典
    # 再通过建立env.filters的键值对建立过滤器
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    # 将jinja环境赋给app的__templating__属性
    app['__templating__'] = env

# 在处理请求之前，先记录日志
async def logger_factory(app, handler):
    async def logger(request):
        # 记录日志，包括http method， path
        logging.info('Request: %s %s' % (request.method, request.path))
        # await asyncio.sleep(0.3)
        # 日志记录完毕后，调用传入的handler继续处理请求
        return (await handler(request))
    return logger

# 解析数据
async def data_factory(app, handler):
    async def parse_data(request):
        # 解析数据是针对post方法传来的数据，如果不是post，就跳过，直接调用handler处理请求
        if request.method == 'POST':
            # content_type表示post的消息主题的类型，以application/json开头表示消息主体为json
            if request.content_type.startswith('application/json'):
                # request.json()方法读取消息主体，并以utf-8解码
                # 将消息主体存入请求的__data__属性
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            # 以application/x-www-form-urlencoded开头的是浏览器表单
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                # request.post()来读取表单信息
                request.__data__ = await request.post()
                logging.info('request form: %s' % str(request.__data__))
        # 调用传来的handler继续处理请求
        return (await handler(request))
    return parse_data

# 上面是在url处理函数之前处理了请求，以下则在url处理函数之后进行处理
# 将request handler的返回值转换为web.response对象
async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        # 调用handler来处理url请求，并返回响应结果
        r = await handler(request)
        # 如果响应结果是web.StreamResponse，直接返回
        # StreamResponse是aiohttp定义response的基类,即所有响应类型都继承自该类
        # StreamResponse主要为流式数据而设计
        if isinstance(r, web.StreamResponse):
            return r
        # 如果响应结果为字节流，则将其作为应答的body部分并设置响应类型为流型
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        # 若响应结果为字符串
        if isinstance(r, str):
            # 判断相应结果是否为重定向，是则返回重定向的地址
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            # 不是，则以utf-8对字符串进行编码，作为body，设置响应的相应类型
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        # 若响应结果为dict，则获取它的模板属性，这里是jinja2.env
        if isinstance(r, dict):
            template = r.get('__template__')
            # 如果不存在模板，则将dict调整为json格式返回，并设置响应类型为json
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            #　存在模板的就套用模板，用request handler的结果进行渲染
            else:
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        # 若响应结果为整形
        # 此时r为状态码，即404,500等
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        # 若响应为tuple，且长度为2
        if isinstance(r, tuple) and len(r) == 2:
            # t是状态码，m是错误描述
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                # 返回状态码和错误描述
                return web.Response(t, str(m))
        # 默认用字符形式返回相应结果，设置文本类型为普通文本
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response

# 时间过滤器
def datetime_filter(t):
    # 定义时间差
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

# 初始化
# loop指的是循环线程
async def init(loop):
    # 创建全局数据库连接池
    await orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='www', password='www', db='awesome')
    # 创建web应用
    app = web.Application(loop = loop, middlewares=[
        logger_factory, response_factory
    ])

    #创建一个Application实例
    # 设置模板为jinja2，并用时间为过滤器
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    # 注册所有url处理函数
    add_routes(app, "handlers")
    # 将当前目录下的static目录加入app目录
    add_static(app)
    # 调用子协程:创建一个TCP服务器,绑定到"127.0.0.1:9000"socket,并返回一个服务器对象
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')#发送日志
    return srv

loop = asyncio.get_event_loop()# 获取当前内容的事件循环
loop.run_until_complete(init(loop))# 执行coroutine，也就是init(loop)
# 一直在不停地执行，不停地loop
loop.run_forever()