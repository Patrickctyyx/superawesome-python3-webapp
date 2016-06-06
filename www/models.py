import time,uuid#有了uuid不需考虑数据库建立时的名称重复问题
from orm import Model,StringField,BooleanField,FloatField,TextField

# 用当前时间与随机生成的uuid合成作为id
def next_id():
    # uuid4()以随机方式生成uuid,hex属性将uuid转为32位的16进制数
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

class User():
    # __table__的值将在创建类时被映射为表名
    __table__='users'

    #括号里面都是默认值
    # 此处default用于存储每个用于独有的id,next_id将在insert的时候被调用
    id=StringField(primary_key=True,default=next_id(),ddl='varchar(50)')
    email=StringField(ddl='varchar(50)')
    password = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    # 此处default用于存储创建的时间,在insert的时候被调用
    create_at=FloatField(default=time.time)

class Blog(Model):
    __table__ = 'blogs'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    name = StringField(ddl='varchar(50)')
    summary = StringField(ddl='varchar(200)')
    content = TextField()
    created_at = FloatField(default=time.time)

class Comment(Model):
    __table__ = 'comments'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    blog_id = StringField(ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)



