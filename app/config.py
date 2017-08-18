# encoding: utf-8

import os
import pymysql

DEBUG = True
SECRET_KEY = os.urandom(24)

#数据库配置
HOSTNAME = '127.0.0.1'
PORT = '3306'
DATABASE = 'movie'
USERNAME = 'root'
PASSWORD = '123456'
DB_URI = 'mysql+pymysql://{}:{}@{}:{}/{}?charset=utf8'.format(USERNAME,
                                                              PASSWORD, HOSTNAME, PORT, DATABASE)
SQLALCHEMY_DATABASE_URI = DB_URI
SQLALCHEMY_TRACK_MODIFICATIONS = False


#上传文件目录
UP_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "static/uploads/")

#会员头像目录
FACE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "static/uploads/users/")

#redis配置
REDIS_URL="redis://127.0.0.1:6379/0"