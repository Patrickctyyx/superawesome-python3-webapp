import asyncio, logging

import aiomysql

#打印sql日志
def log(sql, args=()):
    logging.info('SQL: %s' % sql)

#全局的连接池
@asyncio.coroutine
def create_pool(loop,**kw):
    #kw是一个dict
    logging.info('create database connection pool...')
    global __pool
    __pool=yield from aiomysql.create_pool(
        #yield from个人理解就是用协程，返回的结果还是后面函数的返回结果，这里__pool得到的就是一个pool对象
        # dict.get(key, default),如果key存在，就返回对应值，不存在就返回default这个的值
        host=kw.get('host','localhost'),# 数据库服务器的位置,设在本地
        port=kw.get('port',3306),# mysql的端口
        user=kw['user'], # 登录用户名
        password=kw['password'],#密码
        db=kw['db'],# 当前数据库名
        charset=kw.get('charset','utf8'), # 设置连接使用的编码格式为utf-8
        autocommit=kw.get('autocommit',True),# 自动提交模式,此处默认是False
        maxsize=kw.get('maxsize',10),
        minsize=kw.get('minsize',1),
        loop=loop # 设置消息循环
    )

#执行SQL的SELECT语句
@asyncio.coroutine
def select(sql,args,size=None):
    log(sql,args)
    global __pool#使用全局变量__pool
    with (yield from __pool) as conn:#从连接池获取数据库连接
        #with...as（简化try finally）的用法：先调用with后面的表达式中的__enter__ ，把返回值给as后面的表达式，再运行下面的命令，完后调用__exit__
        #可以使用with的类型（with后面的表达式）必须实现__enter__ __exit__
        cur=yield from conn.cursor(aiomysql.DictCursor)#建立curosor（游标），以dict返回结果
        #cursor是用来实现python语句操作sql命令
        yield from cur.execute(sql.replace('?','%s'),args or ())#用？代替掉%s，因为SQL语句的占位符是?，而MySQL的占位符是%s
        if size:#size参数默认为none，如果传入了
            rs=yield from cur.fetchmany(size)#就获取指定数量的查询信息
        else:
            rs=yield from cur.fetchall()#没传入就获取所有查询信息
        yield from cur.close()#关闭游标
        logging.info('rows returned %s'%len(rs))
        return rs

#执行SQL的INSERT、UPDATE、DELETE（增删改）语句
@asyncio.coroutine
def execute(sql,args):
    log(sql)
    with (yield from __pool) as conn:
        try:
            cur=yield from conn.cursor()#打开普通游标
            yield from cur.execute(sql.replace('?','%s'),args)#还是替换
            affected=cur.rowcount#增删改影响的行数
            yield from cur.close()#关游标
        except BaseException as e:
            raise
        return affected

#ORM
# 构造占位符
def create_args_string(num):
    L = []
    for n in range(num):
        L.append("?")
    return ', '.join(L)# ', '.join(L)意思是把L（list）里面的元素用逗号连接起来生成一个完整的字符串

class Field(object):

    def __init__(self, name, column_type, primary_key, default):
        self.name = name#字段名，如id
        self.column_type = column_type#字段的类型
        self.primary_key = primary_key#主键
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

class StringField(Field):
#ddl("data definition languages"),用于定义数据类型
# varchar("variable char"), 可变长度的字符串,以下定义中的100表示最长长度,即字符串的可变范围为0~100
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)

class IntegerField(Field):

    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, "bigint", primary_key, default)

# 布尔域
class BooleanField(Field):

    def __init__(self, name=None, default=False):
        super().__init__(name, "boolean", False, default)

# 浮点数域
class FloatField(Field):

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, "real", primary_key, default)

# 文本域
class TextField(Field):

    def __init__(self, name=None, default=None):
        super().__init__(name, "text", False, default)

# 这是一个元类,它定义了如何来构造一个类,任何定义了__metaclass__属性或指定了metaclass的都会通过元类定义的构造方法构造类
# 任何继承自Model的类,都会自动通过ModelMetaclass扫描映射关系,并存储到自身的类属性
class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):#这里用来创建类
    #cls：准备创建的类对象，相当于self
    #name：类名，如User
    #bases：父类的tuple
    #attrs：属性的dict，比如User有__table__,id,等
        # 排除Model类本身，因为他就是用来被继承的，不存在和数据库表的映射
        if name=='Model':
            return type.__new__(cls, name, bases, attrs)
        # 以下是针对"Model"的子类的处理,将被用于子类的创建.metaclass将隐式地被继承
        # 获取table（表）名称，如果没定义__table__属性，将name作为表名
        tableName = attrs.get('__table__', None) or name#如果前面的是None就用name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        # 获取所有的Field和主键名:
        mappings = dict()#储存类属性与数据库表的列的映射关系
        fields = []#用于保存除主键外的属性
        primaryKey = None#主键

         # k是属性名,v其实是定义域，如StringField
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k, v))
                mappings[k] = v# 建立映射关系
                if v.primary_key:
                    # 找到主键:
                    if primaryKey:#如果主键已存在，又找到一个，就报错
                        #raise用来报错
                        raise RuntimeError('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)# 将非主键的属性都加入fields列表中
        if not primaryKey:#没有找到主键也报错
            raise RuntimeError('Primary key not found.')
        for k in mappings.keys():# 从类属性中删除已加入映射字典的键,避免重名
            attrs.pop(k)
         # 将非主键的属性变形,放入escaped_fields中,方便增删改查语句的书写
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        #lambda的作用是创建一个函数，把一个字符串变成`%s`这种形式
        #map(function, sequence)：sequence是一个可迭代对象，作用是用sequence里面的值带入到函数function中
        #最后再用list（）将结果变成list
        attrs['__mappings__'] = mappings # 保存属性和列的映射关系
        attrs['__table__'] = tableName#保存表名
        attrs['__primary_key__'] = primaryKey # 主键属性名
        attrs['__fields__'] = fields # 除主键外的属性名，是个dict
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句:
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)

#ORM映射基类,继承自dict,通过ModelMetaclass元类来构造类
class Model(dict,metaclass=ModelMetaclass):
    # 初始化函数,调用其父类(dict)的方法
    def __init__(self,**kw):
        super(Model,self).__init__(**kw)

    # 增加__getattr__方法,使获取属性更方便,即可通过"a.b"的形式
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'"%key)

    # 增加__setattr__方法,使设置属性更方便,可通过"a.b=c"的形式
    def __setattr__(self, key, value):
        self[key] = value

     # 通过键取值,若值不存在,返回None
    def getValue(self, key):
        return getattr(self, key, None)

    # 通过键取值,若值不存在,则返回默认值
    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key] # field是一个定义域!比如StringField【这里用了前面__setattr__，相当于self【__mappings__】[key]】
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                # 通过default取到值之后再将其作为当前值
                setattr(self, key, value)
        return value

    # classmethod装饰器将方法定义为类方法
    # 对于查询相关的操作,我们都定义为类方法,就可以方便查询,而不必先创建实例再查询
    @classmethod
    @asyncio.coroutine
    def find(cls, pk):
        ' find object by primary key. pk就是主键'
        # 我们之前已将将数据库的select操作封装在了select函数中,以下select的参数依次就是sql, args, size
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)#cls.__select__也用了前面的getattr方法
        if len(rs) == 0:
            return None
        # **表示关键字参数
        return cls(**rs[0])
        #*args是可变参数，args接收的是一个tuple；
        #**kw是关键字参数，kw接收的是一个dict。
        #使用*args和**kw是Python的习惯写法，当然也可以用其他参数名，但最好使用习惯用法

    @asyncio.coroutine
    def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = yield from execute(self.__insert__, args)
        if rows != 1:
            logging.warning('failed to insert record: affected rows: %s' % rows)





