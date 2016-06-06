# -*- coding: utf-8 -*-

'Web App骨架'

__author__ = 'Patrick'


import logging;logging.basicConfig(level=logging.INFO)
import asyncio,os,json,time
from datetime import datetime
from aiohttp import web

def index(request):
    # 这是个 request handler
    # 接受请求，返回一个实例并响应请求
    return web.Response(body = b'<h1>Awesome</h1>')

@asyncio.coroutine
def init(loop):
    #loop指的是循环线程
    app = web.Application(loop = loop)
    #创建一个Application实例
    app.router.add_route('GET', '/', index)
    #在这个http方法【get】和路径【/】下注册 request handler
    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    #创建TCP服务器，参数绑定服务器和端口
    logging.info('server started at http://127.0.0.1:9000...')#发送日志
    return srv

loop = asyncio.get_event_loop()#获取当前内容的事件循环
loop.run_until_complete(init(loop))#执行coroutine，也就是init(loop)
#一直在不停地执行，不停地loop
loop.run_forever()