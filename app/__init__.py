# encoding: utf8

from flask import Flask, render_template
from app import config
from app.exts import db
from flask.ext.redis import FlaskRedis

app = Flask(__name__)
app.config.from_object(config)
db.init_app(app)
rd = FlaskRedis(app)

'''
***手动把App 的 App Context 推入栈中***
说明：编写一个离线脚本时，如果直接在一个 Flask-SQLAlchemy 写成的 Model 上调用类似 User.query.get(user_id) 的查询，
就会遇到以下报错： 
RuntimeError： application not registered on db instance and no applicationbound to current context

因为此时 App Context 还没被推入栈中，而 Flask-SQLAlchemy 需要数据库连接信息时就会去取 current_app.config，current_app 
指向的却是 _app_ctx_stack 为空的栈顶。解决的办法是运行脚本正文之前，先将 App 的 App Context 推入栈中，栈顶不为空后 current_app 
这个 Local Proxy 对象就自然能将“取 config 属性” 的动作转发到当前 App 上了
'''
from app import app
app.app_context().push()

'''
***手动把App 的 App Context 推入栈中***
'''


from app.home import home as home_blueprint
from app.admin import admin as admin_blueprint

app.register_blueprint(home_blueprint)
app.register_blueprint(admin_blueprint, url_prefix='/admin')


@app.errorhandler(404)
def page_not_found(error):
    return render_template("home/404.html")


if __name__ == '__main__':
    app.run()


