# ！-*- coding: utf-8 -*-

__author__ = 'Patrick'

'url handlers'

import re
import time
import json
import logging
import hashlib
import base64
import asyncio

from coroweb import get,post

from models import User,Comment,Blog,next_id

@get('/')
def index(request):
    # summary用于在博客首页上现实的句子
    summary = 'Daily growing.'
    # 手动写了blogs的list，并没有将其存入数据库
    blogs = [
        Blog(id='1', name='Test1 Blog', summary=summary, created_at=time.time()-120),
        Blog(id='2', name='Test2 Blog', summary=summary, created_at=time.time()-3600),
        Blog(id='3', name='Test3 Blog', summary=summary, created_at=time.time()-7200),
    ]
    # 返回一个dict，指示了使用何种模板，以及内容
    # app.py的response_factory将会对handler的返回值进行分类处理
    return {
        '__template__': 'blogs.html',
        'users': blogs
    }


@get('/api/users')
def api_get_users():
    users = yield from User.findAll(orderBy='created_at desc')
    for u in users:
        u.passwd = '******'
    return dict(users=users)