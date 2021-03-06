# encoding: utf8

from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager
from app import app
from app.exts import db
from app.models import User, Userlog, Tag, Movie, Preview, Comment, Moviecol, Auth, Role, Admin, Adminlog, Oplog

manager = Manager(app)

# 使用Migrate绑定app和db
migrate = Migrate(app, db)

# 添加迁移脚本的命令到manager中
manager.add_command('db', MigrateCommand)

if __name__ == "__main__":
    # manager.run()   #管理数据库时使用
    app.run()         #作为程序入口时使用

