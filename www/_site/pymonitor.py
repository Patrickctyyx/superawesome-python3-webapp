# -*- coding: utf-8 -*-

'''自动检查www目录下的.py文件修改情况
用该脚本启动app.py则当前目录下任意.py文件被修改后，服务器将自动重启'''

__author__ = 'Patrick'

import os
import sys
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 打印日志信息
def log(s):
    print('[Monitor] %s' % s)

# 自定义的文件系统事件处理器
class MyFileSystemEventHandler(FileSystemEventHandler):

    def __init__(self, fn):
        super(MyFileSystemEventHandler, self).__init__()
        self.restart = fn

    # 覆盖on_any_event方法
    #　这个方法捕捉所有时间，文件或目录的创建，删除，修改等
    # 在这里只处理python脚本的事件
    def on_any_event(self, event):
        if event.src_path.endswitch('.py'):
            log('Python source file changed: %s' % event.src_path)
            self.restart()

command = ['echo', 'ok']
process = None

# 杀死进程函数
def kill_process():
    global process
    if process:
        log('Kill process [%s] ...' % process.pid)
        # process指向Popen对象，在下面的start_process被创建
        process.kill()
        process.wait() # 等待进程终止，并返回一个结果码
        log('Process ended with code %s.' % process.returncode)
        process = None

# 创建新进程
def start_process():
    global process, command
    log('Start process %s ...' % ' '.join(command))
    # subprocess.Popen是一个进场构造器，它在一个新的进程中执行子进程
    # command是一个list，此时将被执行的程序应为序列的第一个元素，此处为python3
    process = subprocess.Popen(command, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)

# 重启进程
def restart_process():
    kill_process()
    start_process()

def start_watch(path, callback):
    observer = Observer() # 创建监视器对象
    # 为监视器对象安排时间表，即将处理器，路径注册到监视器对象上
    # 重启进程函数绑定在处理器的restart属性上
    # 表示递归，即当前目录的子目录也在被监视范围内
    observer.schedule(MyFileSystemEventHandler(restart_process), path, recursive=True)
    observer.start()
    log('Watching directory %s ...' % path)
    start_process()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    argv = sys.argv[1:] # sys.argv[0]表示当前被执行的脚本
    if not argv:
        print('Usage: ./pymonitor your_script.py')
        exit(0)
    if argv[0] != 'python3':
        argv.insert(0, 'python3')
    command = argv
    path = os.path.abspath('.') # 获取当前目录的绝对路径，‘.’表示当前目录
    start_watch(path, None)

