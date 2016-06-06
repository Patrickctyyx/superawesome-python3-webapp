import orm,asyncio
from models import User, Blog, Comment
import sys


def test(loop):
    yield from orm.create_pool(loop=loop,user='root', password='ctyyx', db='awesome')

    u = User(id='cty',name='Test', email='test@example.com', password='1234567890', image='about:blank')

    yield from u.save()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test(loop))
    loop.close()
    if loop.is_closed():
        sys.exit(0)
