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
import markdown2
from aiohttp import web
from coroweb import get, post
from models import User, Comment, Blog, next_id
from apis import APIError, APIValueError, APIResourceNotFoundError, APIPermissionError, Page
from config import configs

# 此处所有的handler都会在app.py中通过add_routes自动注册到app.router上

COOKIE_NAME = 'awesome'
_COOKIE_KEY = configs.session.secret

# 验证用户身份
def check_admin(request):
    # 检查用户是不会是管理员
    # 对于登录的用户，检查admin属性，管理员的为真
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()

# 取得页码
def get_page_index(page_str):
    # 检查传入字符的合法性
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        return p

# 文本变成html
def text2html(text):
    # 先用filter函数睿输入的文本进行过滤处理，断行，去除首尾空白字符
    # 再用map函数对特殊符号进行转换，在字符串装入html的<p>中
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;', filter(lambda s: s.strip() != '', text.spilt('\n'))))
    # lines是一个字符串list，将其组装成一个字符串表示html的段落
    return ''.join(lines)

# 通过用户信息计算加密cookie
def user2cookie(user, max_age):
    '''Generate cookie str by user.'''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age)) # expires（失效时间）是当前时间加上cookie最大存活时间的字符串
    # 利用用户id，加密后的密码，失效时间，加上cookie的密钥，组合成待加密的原始字符串
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    # 生成加密的字符串，并与用户id，失效时间共同组合成cookie
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

# 解密cookie
@asyncio.coroutine
def cookie2user(cookie_str):
    '''Parse cookie and load user if cookie is valid'''
    # cookie_str就是user2cookie函数的返回值
    if not cookie_str:
        return None
    try:
        # 解密是加密的逆向过程，所以先通过’-‘拆分cookie，得到加密的字符串，用户id，失效时间
        L = cookie_str.spilt('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time(): # 失效时间小于当前时间表明cookie已失效
            return None
        user = yield from User.find(uid) # 拆分的道德id在数据库中查找用户信息
        if user is None:
            return None
        # 利用用户id,加密后的密码,失效时间,加上cookie密钥,组合成待加密的原始字符串
        # 再对其进行加密,与从cookie分解得到的sha1进行比较.若相等,则该cookie合法
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')):
            logging.info('invalid sha1')
            return None
        # 以上就完成了cookie的验证
        # 验证cookie就是为了验证用户是否仍登录，从而使用户不必重新登录
        # 因此返回用户信息即可
        user.passwd = '*****'
        return user
    except Exception as e:
        logging.exception(e)
    return None

# 对于首页的get请求的处理
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

# 返回注册界面
@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }

# 返回登录界面
@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }

# 用户登出
@get('/signout')
def signout(request):
    # 请求头部的referer，表示上一个界面
    # 用户等出时，实际转到了/signout路径下，因此为了使登出没有违和感，获得“当前”url
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

# 博客详情页
@get('/blog/{id}')
def get_blog(id):
    blog = yield from Blog.find(id) # 通过id从数据库拉取博客信息
    # 从数据库拉取指定blog的所有评论，按时间顺序降序排序
    comments = yield from Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    # 将每条评论都转化成html格式
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content) # blog是markdown格式，转化成html
    return {
        # 返回的参数将在jinja2模板中被解析
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }

# 写博客的界面
@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '', # id传给js变量I
        # action传给js变量action
        # 将在用户提交博客的时候将数据post到action指定的路径，此处即为博客创建的api
        'action': '/api/blogs'
    }

# 修改博客的界面
@get('/manage/')
def manage():
    return 'redirect:/manage/comments'

# 管理博客的页面
@get('/manage/blogs')
def manage_blogs(*, page='1'): # 管理界面默认从1开始
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page) # 通过page_index来显示分页
    }

# 管理评论的界面
@get('/manage/comments')
def manage_comments(*, page='1'):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page) # 通过page_index来显示分页
    }

# 管理用户的界面
@get('/manage/users')
def manage_comments(*, page='1'):
    return {
        '__template__': 'manage_users.html',
        'page_index': get_page_index(page) # 通过page_index来显示分页
    }

#　API:用户信息接口,用于返回机器能识别的用户信息,获取用户信息
@get('/api/users')
def api_get_users(*, page='1'):
    page_index = get_page_index(page)
    num = yield from User.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = yield from User.findAll(orderBy='created_at desc')
    for u in users:
        u.passwd = '******'
    return dict(users=users)

# 匹配邮箱与加密后的密码的正则表达式
_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'[0-9a-f]{40}$')

# API:这是实现用户注册的api，注册到/api/users路径上，http method为post
@post('/api/users')
def api_register_user(*, name, email, passwd):
    # 验证输入的正确性
    # Python strip() 方法用于移除字符串头尾指定的字符（默认为空格）
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    # 在数据库里查看是否已存在该email
    users = yield from User.findAll('email=?', [email])# mysql参数被列在list里面
    if len(users) > 0: # findAll结果不为0，表示数据库已存在同名email
        raise  APIError('register:failed', 'email', 'Email is already in use.')

    # 数据库没有相应的email信息
    uid = next_id() # 利用当前时间随机生成的uuid生成user id
    sha1_passwd = '%s:%s' %(uid, passwd) # 将user id与密码的组合赋给sha1_passwd
    # 创建用户对象, 其中密码并不是用户输入的密码,而是经过复杂处理后的保密字符串
    # hexdigest()函数将hash对象转换成16进制表示的字符串
    # Gravatar(Globally Recognized Avatar)是一项用于提供在全球范围内使用的头像服务。只要在Gravatar的服务器上上传了你自己的头像，便可以在其他任何支持Gravatar的博客、论坛等地方使用它。此处image就是一个根据用户email生成的头像
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image="http://www.gravatar.com/avatar/%s?d=mm&s=120" % hashlib.md5(email.encode('utf-8')).hexdigest())
    yield from user.save() # 将用户信息储存到数据库中

    # 这其实还是一个handler，因此要返回response，此时返回的response是带有cookie的响应
    r = web.Response()
    # 刚创建的的用户设置cookie(网站为了辨别用户身份而储存在用户本地终端的数据)
    # http协议是一种无状态的协议,即服务器并不知道用户上一次做了什么.
    # 因此服务器可以通过设置或读取Cookies中包含信息,借此维护用户跟服务器会话中的状态
    # user2cookie设置的是cookie的值
    # max_age是cookie的最大存活周期,单位是秒.当时间结束时,客户端将抛弃该cookie.之后需要重新登录
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '*****' # 修改密码的外部显示为*
    # 设置content_type, 将在data_factory中间件中继续处理
    r.content_type = 'application/json'
    # json.dumps方法将对象序列化为json格式
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

# 用户登录验证的api
@post('/api/authenticate')
def authenticate(*, email, passwd):
    # 验证邮箱与密码的合法性
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:
        raise APIValueError('passwd', 'Invalid passwd.')
    users = yield from User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exists.')
    user = users[0] # 获得用户记录，返回的记录是list
    # 验证密码
    # 数据库中存储的并非原始的用户密码,而是加密的字符串
    # 我们对此时用户输入的密码做相同的加密操作,将结果与数据库中储存的密码比较,来验证密码的正确性
    # 以下步骤合成为一步就是:sha1 = hashlib.sha1((user.id+":"+passwd).encode("utf-8"))
    # 对照用户时对原始密码的操作(见api_register_user),操作完全一样
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid password.')
    # 用户登录之后,同样的设置一个cookie,与注册用户部分的代码完全一样
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = "*****"
    r.content_type = "application/json"
    r.body = json.dumps(user, ensure_ascii=False).encode("utf-8")
    return r

# API:获取blogs
@get('/api/blogs')
def api_blogs(*, page='1'):
    page_index = get_page_index(page)
    num = yield from Blog.findNumber('count(id)') # num为博客总数
    p =Page(num, page_index) # 创建page对象
    if num ==0:
        return dict(page=p, blogs=())
    # 博客书不为0就从数据库中抓取博客
    # limit强制select返回指定的记录数
    blogs = yield from Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs) # 返回dict，以供response的中间件处理

# API：获取单条日志
@get('/api/blogs/{id}')
def api_get_blog(*, id):
    blog = yield from Blog.find(id)
    return blog

# API：创建blog
@post('/api/blogs')
def api_create_blog(request, *, name, summary, content):
    check_admin(request) # 检查用户权限
    # 验证博客信息的合法性
    if not name or not name.strip():
        raise APIValueError("name", "name cannot be empty")
    if not summary or not summary.strip():
        raise APIValueError("summary", "summary cannot be empty")
    if not content or not content.strip():
        raise APIValueError("content", "content cannot be empty")
    # 创建博客对象
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
    yield from blog.save() # 储存博客入数据库
    return blog # 返回博客信息

# API：修改博客
@post('/api/blogs/{id}')
def api_update_blog(id, request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError("name", "name cannot be empty")
    if not summary or not summary.strip():
        raise APIValueError("summary", "summary cannot be empty")
    if not content or not content.strip():
        raise APIValueError("content", "content cannot be empty")
    blog = yield from Blog.find(id) # 获取修改前的博客
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    yield from blog.update() # 更新博客
    return blog

# API:删除博客
@post('/api/blogs/{id}/delete')
def api_delete_blog(request, *, id):
    check_admin(request)
    # 根据model类的定义，只有查询才是类方法，其他删改都是实例方法
    # 所以要先创建一个实例
    blog = yield from Blog.find(id)
    yield from blog.remove()
    return dict(id=id) # 返回被删除博客的id

# API：获取评论
@get('/api/comments')
def api_comments(*, page='1'):
    page_index = get_page_index(page)
    num = yield from Comment.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, comments=())
    comments = yield from Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)

# API: 创建评论
@post('/api/blogs/{id}/comments')
def api_create_comment(id, request, *, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please sign in first.')
    if not content or not content.strip():
        raise APIValueError('content', 'Content cannot be empty.')
    blog = yield from Blog.find(id)
    if blog is None:
        raise APIResourceNotFoundError('Blog', 'No such a blog.')
    comment = Comment(user_id=user.id, user_name=user.name, user_image=user.image, blog_id = blog.id, content=content.strip())
    yield from content.save()
    return comment

# API:删除评论
@post('/api/blogs/{id}/delete')
def api_delete_comment(id, request):
    check_admin(request)
    comment = yield from Comment.find(id)
    if comment is None:
        raise APIResourceNotFoundError('Comment', 'No such a comment.')
    yield from comment.remove()
    return dict(id=id)