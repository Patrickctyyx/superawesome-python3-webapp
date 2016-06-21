#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'Json API definition'

__author__ = 'Patrick'

import json
import logging
import inspect # the module provides several useful functions to help get information about live objects, such as modules, classes, methods, functions.
import functools # 该模块提供有用的高阶函数.总的来说,任何callable对象都可视为函数


# page对象,用于储存分页信息
class Page(object):
    '''Page object for diaplay pages.'''

    def __init__(self, item_count, page_index=1, page_size=10):
        '''init Pagination by
        item_count 博客总数
        page_index 页码
        page_size 一个页面最多显示博客的数目'''
        self.item_count = item_count
        self.page_size = page_size
        # 页面数目由博客总数和一个页面最多显示博客的数目共同决定
        # 如果最后一页达不到page_size，仍然独立一页
        self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)
        if (item_count == 0) or (page_index > self.page_count):
            self.offset = 0 # offset为偏移量，即前面所有页博客的总数
            self.limit = 0 # limit为限制数目，这两个用来获得博客的api
            self.page_index = 1
        else:
            self.page_index = page_index # 页码设置为指定的页码
            self.offset = self.page_size * (page_index - 1)
            self.limit = self.page_size # 博客限制数与页面大小一致
        self.has_next = self.page_index < self.page_count # 页码小于页面总数就没有下页
        self.has_previous = self.page_index > 1 # 页码大于1就有前页

    def __str__(self):
        # 返回页面信息
        return "item_count: %s, page_count: %s, page_index: %s, page_size: %s, offset: %s, limit: %s" % (self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit)

    __repr__ = __str__


class APIError(Exception):
    '''
    定义APIError基类,其继承自Exception类,具有它的一切功能
    '''
    def __init__(self, error, data="", message=""):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message

class APIValueError(APIError):
    '''
    定义APIValueError类
    表明输入的值错误或不合法.
    data属性指定为输入表单的错误域
    '''
    def __init__(self, field, message=""):
        super(APIValueError, self).__init__("value:invalid", field, message)


class APIResourceNotFoundError(APIError):
    '''
    定义APIResourceNotFoundError类
    表明找不到指定资源.
    data属性指定为资源名
    '''
    def __init__(self, field, message=""):
        super(APIResourceNotFoundError, self).__init__("value:notfound", field, message)

class APIPermissionError(APIError):
    '''
    定义APIPermissionError类
    表明没有权限
    '''
    def __init__(self, message=""):
        super(APIPermissionError, self).__init__("permission:forbidden", "permission", message)