# encoding: utf8

from . import home
from flask import render_template, redirect, url_for, flash, session, request, Response
from app.home.forms import RegistForm, LoginForm, UserdetailForm, PwdForm, CommentForm
from app.models import User, Userlog, Preview, Tag, Movie, Comment, Moviecol
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from app.exts import db
import uuid
from functools import wraps
import os
from app.config import FACE_DIR
import datetime
from app import rd


# 登录装饰器
def user_login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_logged_in' in session:
            return func(*args, **kwargs)
        return redirect(url_for('home.login', next=request.url))

    return wrapper


# 修改文件名称
def change_filename(filename):
    file_extention = (os.path.splitext(filename))[1]  # 分离文件的路径，获取文件扩展名
    filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S") + \
               str(uuid.uuid4().hex) + file_extention
    return filename


# 首页
@home.route("/<int:page>/", methods=["GET"])
def index(page=None):
    if page == None:
        page = 1

    tags = Tag.query.all()

    #分页
    page_data = Movie.query

    tid = request.args.get("tid", 0)  # 标签(注：如果tid为空，则给它赋值0，后面以此类推）
    if int(tid) != 0:
        page_data = page_data.filter_by(tag_id=int(tid))

    star = request.args.get("star", 0)  # 星级
    if int(star) != 0:
        page_data = page_data.filter_by(star=int(star))

    time = request.args.get("time", 0)  # 时间(1表示"最近"，2表示"更早")
    if int(time) == 1:
        page_data = page_data.order_by(Movie.addtime.desc())
    elif int(time) == 2:
        page_data = page_data.order_by(Movie.addtime.asc())

    pm = request.args.get("pm", 0)  # 播放数量（1表示 从高到底，2表示 从低到高）
    if int(pm) == 1:
        page_data = page_data.order_by(Movie.playnum.desc())
    elif int(pm) == 2:
        page_data = page_data.order_by(Movie.playnum.asc())

    cm = request.args.get("cm", 0)  # 评论数量（1表示 从高到底，2表示 从低到高）
    if int(cm) == 1:
        page_data = page_data.order_by(Movie.commentnum.desc())
    elif int(cm) == 2:
        page_data = page_data.order_by(Movie.commentnum.asc())

    page_data = page_data.paginate(page=page, per_page=10)

    p = dict(
        tid=tid,
        star=star,
        time=time,
        pm=pm,
        cm=cm
    )

    return render_template("home/index.html", tags=tags, p=p, page_data=page_data)


# 登录
@home.route("/login/", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        data = form.data
        user = User.query.filter_by(name=data.get('name')).first()
        if not user.check_pwd(data.get('pwd')):
            flash('身份验证失败！', 'err')
            return redirect(url_for('home.login'))
        session['user_logged_in'] = True
        session['user_name'] = user.name
        session['user_id'] = user.id

        userlog = Userlog(
            user_id=user.id,
            ip=request.remote_addr,
        )
        db.session.add(userlog)
        db.session.commit()
        return redirect(request.args.get("next") or url_for('home.index', page=1))
    return render_template("home/login.html", form=form)


# 退出
@home.route("/logout/")
@user_login_required
def logout():
    # session.clear()   #这种方法太粗暴，某些情况下会影响flash的消息闪现，不推荐使用
    session.pop('user_logged_in', None)
    session.pop('user_name', None)
    session.pop('user_id', None)
    return redirect(url_for('home.login'))


# 会员注册
@home.route("/register/", methods=["GET", "POST"])
def register():
    form = RegistForm()
    if form.validate_on_submit():
        data = form.data
        user = User(
            name=data.get('name'),
            pwd=generate_password_hash(data.get('repwd')),
            email=data.get('email'),
            phone=data.get('phone'),
            uuid=uuid.uuid4().hex
        )
        db.session.add(user)
        db.session.commit()
        flash('注册成功，请登录!', 'ok')
        return redirect(url_for('home.login'))
    return render_template("home/register.html", form=form)


# 会员资料
@home.route("/user/", methods=["GET", "POST"])
@user_login_required
def user():
    form = UserdetailForm()
    # 查询并显示用户原有信息
    # user = User.query.get(int(session['user_id']))
    user = User.query.filter_by(name=session.get('user_name')).first()
    if request.method == "GET":
        form.email.data = user.email
        form.phone.data = user.phone
        form.info.data = user.info
    # 进入会员资料修改页面时，头像可以不修改
    form.face.validators = []

    if form.validate_on_submit():
        data = form.data
        # 处理不允许重复的值
        email_count = User.query.filter_by(email=data.get('email')).count()
        if email_count == 1 and user.email != data.get('email'):
            flash('该邮箱已存在!', 'err')
            return redirect(url_for('home.user'))
        phone_count = User.query.filter_by(phone=data.get('phone')).count()
        if phone_count == 1 and user.phone != data.get('phone'):
            flash('该手机号码已存在!', 'err')
            return redirect(url_for('home.user'))
        # file_face 不为空，说明用户上传了新头像， 获取并保存新头像
        file_face = secure_filename(form.face.data.filename)
        if file_face != "":
            if not os.path.exists(FACE_DIR):
                os.makedirs(FACE_DIR)
                os.chmod(FACE_DIR, "rw")
            user.face = change_filename(file_face)
            form.face.data.save(FACE_DIR + user.face)
        # 获取其他项
        user.email = data.get('email')
        user.phone = data.get('phone')
        user.info = data.get('info')
        # 更新数据库
        db.session.add(user)
        db.session.commit()
        flash('会员资料修改成功!', 'ok')
        return redirect(url_for('home.user'))
    return render_template("home/user.html", form=form, user=user)


# 修改密码
@home.route("/pwd/", methods=["GET", "POST"])
@user_login_required
def pwd():
    form = PwdForm()
    if form.validate_on_submit():
        data = form.data
        user = User.query.filter_by(name=session.get('user_name')).first()
        user.pwd = generate_password_hash(data.get('new_pwd'))
        db.session.add(user)
        db.session.commit()
        flash('密码修改成功，请重新登录!', 'ok')
        return redirect(url_for('home.logout'))
    return render_template("home/pwd.html", form=form)


# 会员评论
@home.route("/comments/<int:page>/")
@user_login_required
def comments(page=None):
    if page == None:
        page = 1
    page_data = Comment.query.join(Movie).join(User).filter(
        Movie.id == Comment.movie_id, User.id == session.get('user_id')).order_by(
        Comment.addtime.desc()).paginate(page=page, per_page=3)
    return render_template("home/comments.html", page_data=page_data)


# 会员登录日志
@home.route("/loginlog/<int:page>/", methods=["GET"])
@user_login_required
def loginlog(page=None):
    if page is None:
        page = 1
    page_data = Userlog.query.join(User).filter(
        User.id == Userlog.user_id).order_by(
        Userlog.addtime.desc()).paginate(page=page, per_page=10)
    return render_template("home/loginlog.html", page_data=page_data)


# 添加电影收藏
@home.route("/moviecol/add/", methods=["GET"])
@user_login_required
def moviecol_add():
    uid = request.args.get("uid", "")
    mid = request.args.get("mid", "")
    moviecol_count = Moviecol.query.filter_by(
        user_id=int(uid),
        movie_id=int(mid)
    ).count()
    if moviecol_count == 1:   #电影已收藏
        data = dict(ok=0)

    if moviecol_count == 0:   #电影未收藏，执行收藏（存入数据库）
        moviecol = Moviecol(
            user_id=int(uid),
            movie_id=int(mid)
        )
        db.session.add(moviecol)
        db.session.commit()
        data = dict(ok=1)
    import json
    return json.dumps(data)



# 电影收藏
@home.route("/moviecol/<int:page>/")
@user_login_required
def moviecol(page=None):
    if page == None:
        page = 1
    page_data = Moviecol.query.join(Movie).join(User).filter(
        User.id == session.get('user_id'),
        Movie.id == Moviecol.movie_id,
    ).order_by(
        Moviecol.addtime.desc()).paginate(page=page, per_page=3)
    return render_template("home/moviecol.html", page_data=page_data)



# 取消电影收藏，并确保取消收藏后留在当前分页（而不是每次删除后自动跳转回第一页）
@home.route("/moviecol/del/<int:id>/<int:page>/", methods=['GET'])
@user_login_required
def moviecol_del(id=None, page=None):
    moviecol = Moviecol.query.filter_by(movie_id=id).first_or_404()
    db.session.delete(moviecol)
    db.session.commit()
    flash('取消收藏成功!', 'ok')
    return redirect(url_for('home.moviecol', page=page))



# 上映预告，封面轮播效果
@home.route("/animation/")
def animation():
    data = Preview.query.all()
    return render_template("home/animation.html", data=data)


# 搜索
@home.route("/search/<int:page>/")
def search(page=None):
    if page == None:
        page = 1
    key = request.args.get("key", "")  # 获取搜索关键字，默认为空
    page_data = Movie.query.filter(
        Movie.title.ilike('%' + key + '%')).order_by(  # 模糊匹配
        Movie.addtime.desc()).paginate(page=page, per_page=2)
    page_data.key = key
    #获取搜索结果数量
    movie_count = Movie.query.filter(Movie.title.ilike('%' + key + '%')).count()
    return render_template("home/search.html", key=key, page_data=page_data, movie_count=movie_count)


# dplayer播放页面
@home.route("/video/<int:id>/<int:page>/", methods=["GET", "POST"])
def video(id=None, page=None):
    movie = Movie.query.join(Tag).filter(
        Tag.id == Movie.tag_id,
        Movie.id == int(id),
    ).first_or_404()

    #分页
    if page == None:
        page = 1
    page_data = Comment.query.join(Movie).join(User).filter(
        Movie.id == movie.id, User.id == Comment.user_id).order_by(
        Comment.addtime.desc()).paginate(page=page, per_page=3)

    #电影播放数加1并更新数据库（每进入一次play页面，相当于播放了一次电影）
    movie.playnum = movie.playnum + 1
    db.session.add(movie)
    db.session.commit()

    #获取评论相关信息并存入数据库
    form = CommentForm()
    if form.validate_on_submit():
        data = form.data
        comment = Comment(
            content = data.get('content'),
            movie_id = movie.id,
            user_id = session.get('user_id')
        )
        db.session.add(comment)
        db.session.commit()

        #电影评论数加1
        movie.commentnum = movie.commentnum + 1
        # 更新数据库
        flash("添加评论成功!", "ok")
        db.session.add(movie)
        db.session.commit()
        return redirect(url_for('home.video', id=movie.id, page=1))
    return render_template("home/video.html", movie=movie, form=form, page_data=page_data)


# # 原jwplayer播放页面
# @home.route("/play/<int:id>/<int:page>/", methods=["GET", "POST"])
# def play(id=None, page=None):
#     movie = Movie.query.join(Tag).filter(
#         Tag.id == Movie.tag_id,
#         Movie.id == int(id),
#     ).first_or_404()
#
#     #分页
#     if page == None:
#         page = 1
#     page_data = Comment.query.join(Movie).join(User).filter(
#         Movie.id == movie.id, User.id == Comment.user_id).order_by(
#         Comment.addtime.desc()).paginate(page=page, per_page=3)
#
#     #电影播放数加1并更新数据库（每进入一次play页面，相当于播放了一次电影）
#     movie.playnum = movie.playnum + 1
#     db.session.add(movie)
#     db.session.commit()
#
#     #获取评论相关信息并存入数据库
#     form = CommentForm()
#     if form.validate_on_submit():
#         data = form.data
#         comment = Comment(
#             content = data.get('content'),
#             movie_id = movie.id,
#             user_id = session.get('user_id')
#         )
#         db.session.add(comment)
#         db.session.commit()
#
#         #电影评论数加1
#         movie.commentnum = movie.commentnum + 1
#         # 更新数据库
#         flash("添加评论成功!", "ok")
#         db.session.add(movie)
#         db.session.commit()
#         return redirect(url_for('home.play', id=movie.id, page=1))
#     return render_template("home/play.html", movie=movie, form=form, page_data=page_data)



# 弹幕功能函数
@home.route("/tm/", methods=["GET", "POST"])
def tm():
    import json
    if request.method == "GET":
        #获取弹幕消息队列
        id = request.args.get('id')
        key = "movie" + str(id)
        if rd.llen(key):
            msgs = rd.lrange(key, 0, 2999)
            res = {
                "code": 1,
                "danmaku": [json.loads(v) for v in msgs]
            }
        else:
            res = {
                "code": 1,
                "danmaku": []
            }
        resp = json.dumps(res)
    if request.method == "POST":
        #添加弹幕
        data = json.loads(request.get_data())
        msg = {
            "__v": 0,
            "author": data["author"],
            "time": data["time"],
            "text": data["text"],
            "color": data["color"],
            "type": data['type'],
            "ip": request.remote_addr,
            "_id": datetime.datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex,
            "player": [
                data["player"]
            ]
        }
        res = {
            "code": 1,
            "data": msg
        }
        resp = json.dumps(res)
        rd.lpush("movie" + str(data["player"]), json.dumps(msg))
    return Response(resp, mimetype='application/json')