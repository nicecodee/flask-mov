# encoding: utf8

from . import admin
from flask import render_template, redirect, url_for, flash, session, request, abort
from app.admin.forms import LoginForm, TagForm, MovieForm, PreviewForm, \
    PwdForm, AuthForm, RoleForm, AdminForm
from app.models import Admin, Tag, Movie, Preview, User, Comment, Moviecol, \
    Oplog, Adminlog, Userlog, Auth, Role
from functools import wraps
from app.exts import db
from werkzeug.utils import secure_filename
import os
import uuid
import datetime
from app.config import UP_DIR


# 应用上下文处理器
@admin.context_processor
def tpl_extra():
    data = dict(
        online_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    return data

# 写入操作日志
def write_oplog(reason):
    oplog = Oplog(
        admin_id=session.get('admin_id'),
        ip=request.remote_addr,
        reason=reason
    )
    db.session.add(oplog)
    db.session.commit()



# 登录装饰器
def admin_login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'admin_logged_in' in session:
            return func(*args, **kwargs)
        return redirect(url_for('admin.login', next=request.url))
    return wrapper


# 权限控制装饰器（不同角色不同权限，访问不同的页面）
def admin_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        admin = Admin.query.join(Role).filter(
            Role.id == Admin.role_id,
            Admin.id == session["admin_id"]
        ).first()
        auths = admin.role.auths
        auths = list(map(lambda v: int(v), auths.split(",")))  #将列表元素转换为int类型
        auth_list = Auth.query.all()
        urls = [v.url for v in auth_list for val in auths if val == v.id] #遍历列表
        rule = request.url_rule
        if str(rule) not in urls:
            abort(404)
        return f(*args, **kwargs)
    return wrapper


# 修改文件名称
def change_filename(filename):
    file_extention = (os.path.splitext(filename))[1]  # 分离文件的路径，获取文件扩展名
    filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S") + \
               str(uuid.uuid4().hex) + file_extention
    return filename


# 管理首页
@admin.route("/")
@admin_login_required
# # @admin_auth
def index():
    return render_template("admin/index.html")


# 登录
@admin.route("/login/", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        data = form.data
        admin = Admin.query.filter_by(name=data.get('account')).first()
        if not admin.check_pwd(data.get('pwd')):
            flash('身份验证失败！', 'err')
            return redirect(url_for('admin.login'))
        session['admin_logged_in'] = True
        session['admin_name'] = admin.name
        session['admin_id'] = admin.id

        adminlog = Adminlog(
            admin_id=session.get('admin_id'),
            ip=request.remote_addr,
        )
        db.session.add(adminlog)
        db.session.commit()

        return redirect(request.args.get("next") or url_for('admin.index'))
    return render_template("admin/login.html", form=form)


# 退出
@admin.route("/logout/")
@admin_login_required
def logout():
    # session.clear()   #这种方法太粗暴，某些情况下会影响flash的消息闪现，不推荐使用
    session.pop('admin_logged_in', None)
    session.pop('admin_name', None)
    session.pop('admin_id', None)
    return redirect(url_for('admin.login'))


# 修改密码
@admin.route("/pwd/", methods=["GET", "POST"])
@admin_login_required
# @admin_auth
def pwd():
    form = PwdForm()
    if form.validate_on_submit():
        data = form.data
        admin = Admin.query.filter_by(name=session.get('admin_name')).first()
        from werkzeug.security import generate_password_hash
        admin.pwd = generate_password_hash(data.get('new_pwd'))
        db.session.add(admin)
        db.session.commit()
        flash('修改密码成功，请重新登录！', 'ok')
        return redirect(url_for('admin.logout'))

    return render_template("admin/pwd.html", form=form)


# 添加标签
@admin.route("/tag/add/", methods=["GET", "POST"])
@admin_login_required
# @admin_auth
def tag_add():
    form = TagForm()
    if form.validate_on_submit():
        data = form.data
        tag_count = Tag.query.filter_by(name=data.get('name')).count()
        if tag_count == 1:
            flash("标签名称已存在！", "err")
            return redirect(url_for('admin.tag_add'))
        tag = Tag(name=data.get('name'))
        db.session.add(tag)
        db.session.commit()
        flash("添加标签成功！", "ok")

        #写入操作日志
        oplog_reason = "添加标签: %s" % data.get('name')
        write_oplog(oplog_reason)

        return redirect(url_for('admin.tag_add'))
    return render_template("admin/tag_add.html", form=form)


# 标签列表
@admin.route("/tag/list/<int:page>/", methods=["GET"])
@admin_login_required
# @admin_auth
def tag_list(page=None):
    if page is None:
        page = 1
    page_data = Tag.query.order_by(
        Tag.addtime.desc()).paginate(page=page, per_page=5)
    return render_template("admin/tag_list.html", page_data=page_data)


# 删除标签，并确保删除标签后留在当前页面（而不是每次删除后自动跳转回第一页）
@admin.route("/tag/del/<int:id>/<int:page>/", methods=['GET'])
@admin_login_required
# @admin_auth
def tag_del(id=None, page=None):
    tag = Tag.query.filter_by(id=id).first_or_404()
    db.session.delete(tag)
    db.session.commit()

    flash('删除标签成功!', 'ok')

    # 写入操作日志
    oplog_reason = "删除标签: %s" % tag.name
    write_oplog(oplog_reason)

    return redirect(url_for('admin.tag_list', page=page))


# 修改标签
@admin.route("/tag/edit/<int:id>/", methods=["GET", "POST"])
@admin_login_required
# @admin_auth
def tag_edit(id):
    form = TagForm()
    # tag = Tag.query.filter_by(id=id).first_or_404()
    tag = Tag.query.get_or_404(id)
    if form.validate_on_submit():
        data = form.data
        tag_count = Tag.query.filter_by(name=data.get('name')).count()
        if tag.name != data.get('name') and tag_count == 1:
            flash("标签名称已存在！", "err")
            return redirect(url_for('admin.tag_edit', id=id))
        tag.name = data.get('name')
        db.session.add(tag)
        db.session.commit()
        flash("修改标签成功！", "ok")

        return redirect(url_for('admin.tag_edit', id=id))
    return render_template("admin/tag_edit.html", form=form, tag=tag)


# 添加电影
@admin.route("/movie/add/", methods=["GET", "POST"])
@admin_login_required
# @admin_auth
def movie_add():
    form = MovieForm()


    # 添加/删除电影的标签后，实时更新到"添加电影"的标签下拉列表中
    form.tag_id.choices = [(v.id, v.name) for v in Tag.query.all()]

    if form.validate_on_submit():
        data = form.data
        file_url = secure_filename(form.url.data.filename)
        file_logo = secure_filename(form.logo.data.filename)
        if not os.path.exists(UP_DIR):
            os.makedirs(UP_DIR)
            os.chmod(UP_DIR, "rw")
        url = change_filename(file_url)
        logo = change_filename(file_logo)
        url_save_result = form.url.data.save(UP_DIR + url)
        logo_save_result = form.logo.data.save(UP_DIR + logo)
        print("url_save_result: ", url_save_result)
        print("logo_save_result: ", logo_save_result)

        movie = Movie(
            title=data.get('title'),
            url=url,
            info=data.get('info'),
            logo=logo,
            star=int(data.get('star')),
            commentnum=0,
            playnum=0,
            tag_id=int(data.get('tag_id')),
            area=data.get('area'),
            release_time=data.get('release_time'),
            length=data.get('length')
        )
        db.session.add(movie)
        db.session.commit()
        flash("添加电影成功！", "ok")
        return redirect(url_for('admin.movie_add'))
    return render_template("admin/movie_add.html", form=form)


# 电影列表
@admin.route("/movie/list/<int:page>/", methods=["GET"])
@admin_login_required
# @admin_auth
def movie_list(page=None):
    if page is None:
        page = 1
    page_data = Movie.query.join(Tag).filter(Tag.id == Movie.tag_id).order_by(
        Movie.addtime.desc()).paginate(page=page, per_page=5)
    return render_template("admin/movie_list.html", page_data=page_data)


# 删除电影，并确保删除电影后留在当前页面（而不是每次删除后自动跳转回第一页）
@admin.route("/movie/del/<int:id>/<int:page>/filename/", methods=['GET'])
@admin_login_required
def movie_del(id=None, page=None, filename=None):
    # movie = Movie.query.get_or_404(int(id))
    movie = Movie.query.filter_by(id=id).first_or_404()
    db.session.delete(movie)
    db.session.commit()

    flash('删除电影成功!', 'ok')

    # 删除对应的已上传的影片和海报
    file_url = UP_DIR + movie.url
    file_logo = UP_DIR + movie.logo
    print("file_url_remove: ", file_url)
    print("file_logo_remove: ", file_logo)
    os.remove(file_url)
    os.remove(file_logo)

    return redirect(url_for('admin.movie_list', page=page))


# 编辑电影
@admin.route("/movie/edit/<int:id>/", methods=["GET", "POST"])
@admin_login_required
# @admin_auth
def movie_edit(id=None):
    form = MovieForm()

    # 已经存在于数据库且默认可以为空的项，将其validators置为空
    form.url.validators = []
    form.logo.validators = []

    movie = Movie.query.get_or_404(int(id))

    # 以下3项信息需手动查询并赋值给表单才能在页面显示正确结果，如果用form.xxx(value=movie.xxx) 这种
    # 形式将无法显示真实结果，原因未知
    if request.method == "GET":
        form.info.data = movie.info
        form.tag_id.data = movie.tag_id
        form.star.data = movie.star

    if form.validate_on_submit():
        data = form.data

        movie_count = Movie.query.filter_by(title=data.get('title')).count()
        if movie_count == 1 and movie.title != data.get('title'):
            flash("片名已经存在！", "err")
            return redirect(url_for('admin.movie_edit', id=id))

        # 获取需上传文件的修改项
        if form.url.data.filename != "":
            file_url = secure_filename(form.url.data.filename)
            movie.url = change_filename(file_url)
            form.url.data.save(UP_DIR + movie.url)

        if form.logo.data.filename != "":
            file_logo = secure_filename(form.logo.data.filename)
            movie.logo = change_filename(file_logo)
            form.logo.data.save(UP_DIR + movie.logo)

        # 获取其他修改项
        movie.star = data.get('star')
        movie.tag_id = data.get('tag_id')
        movie.info = data.get('info')
        movie.title = data.get('title')
        movie.area = data.get('area')
        movie.length = data.get('length')
        movie.release_time = data.get('release_time')

        db.session.add(movie)
        db.session.commit()

        flash("修改电影成功！", "ok")

        return redirect(url_for('admin.movie_edit', id=movie.id))
    return render_template("admin/movie_edit.html", form=form, movie=movie)


# 添加预告
@admin.route("/preview/add/", methods=["GET", "POST"])
@admin_login_required
# @admin_auth
def preview_add():
    form = PreviewForm()
    if form.validate_on_submit():
        data = form.data

        file_logo = secure_filename(form.logo.data.filename)
        if not os.path.exists(UP_DIR):
            os.makedirs(UP_DIR)
            os.chmod(UP_DIR, "rw")
        logo = change_filename(file_logo)
        form.logo.data.save(UP_DIR + logo)

        preview = Preview(
            title=data.get('title'),
            logo=logo
        )

        db.session.add(preview)
        db.session.commit()

        flash("添加预告成功！", "ok")
        return redirect(url_for('admin.preview_add'))
    return render_template("admin/preview_add.html", form=form)


# 查看预告
@admin.route("/preview/list/<int:page>/", methods=["GET"])
@admin_login_required
# @admin_auth
def preview_list(page=None):
    if page is None:
        page = 1
    page_data = Preview.query.order_by(
        Preview.addtime.desc()).paginate(page=page, per_page=2)
    return render_template("admin/preview_list.html", page_data=page_data)


# 删除预告，并确保删除预告后留在当前页面（而不是每次删除后自动跳转回第一页）
@admin.route("/preview/del/<int:id>/<int:page>/", methods=['GET'])
@admin_login_required
# @admin_auth
def preview_del(id=None, page=None):
    preview = Preview.query.filter_by(id=id).first_or_404()
    db.session.delete(preview)
    db.session.commit()

    flash('删除预告成功!', 'ok')

    return redirect(url_for('admin.preview_list', page=page))


# 修改预告
@admin.route("/preview/edit/<int:id>/", methods=["GET", "POST"])
@admin_login_required
# @admin_auth
def preview_edit(id):
    form = PreviewForm()

    # 已经存在于数据库且默认可以为空的项，将其validators置为空
    form.logo.validators = []

    preview = Preview.query.filter_by(id=id).first_or_404()

    if request.method == "GET":
        form.title.data = preview.title

    if form.validate_on_submit():
        data = form.data

        preview_count = Preview.query.filter_by(title=data.get('title')).count()
        if preview_count == 1 and preview.title != data.get('title'):
            flash("预告标题已经存在！", "err")
            return redirect(url_for('admin.preview_edit', id=id))

        # 获取预告标题
        preview.title = data.get('title')

        # 获取需上传的封面
        if form.logo.data.filename != "":
            file_logo = secure_filename(form.logo.data.filename)
            preview.logo = change_filename(file_logo)
            form.logo.data.save(UP_DIR + preview.logo)

        # 存入数据库
        db.session.add(preview)
        db.session.commit()

        flash("修改预告成功！", "ok")
        return redirect(url_for('admin.preview_edit', id=id))
    return render_template("admin/preview_edit.html", form=form, preview=preview)


# 会员列表
@admin.route("/user/list/<int:page>/", methods=["GET"])
@admin_login_required
# @admin_auth
def user_list(page=None):
    if page is None:
        page = 1
    page_data = User.query.order_by(
        User.addtime.desc()).paginate(page=page, per_page=3)
    for item in page_data.items:
        print("item.face: ", item.face)
    return render_template("admin/user_list.html", page_data=page_data)


# 查看会员信息
@admin.route("/user/view/<int:id>/", methods=["GET"])
@admin_login_required
# @admin_auth
def user_view(id=None):
    user = User.query.get_or_404(int(id))
    return render_template("admin/user_view.html", user=user)


# 删除用户，并确保删除用户后留在当前页面（而不是每次删除后自动跳转回第一页）
@admin.route("/user/del/<int:id>/<int:page>/", methods=['GET'])
@admin_login_required
def user_del(id=None, page=None):
    user = User.query.filter_by(id=id).first_or_404()
    db.session.delete(user)
    db.session.commit()

    flash('删除用户成功!', 'ok')

    return redirect(url_for('admin.user_list', page=page))


# 评论列表
@admin.route("/comment/list/<int:page>/", methods=["GET"])
@admin_login_required
# @admin_auth
def comment_list(page=None):
    if page is None:
        page = 1
    page_data = Comment.query.join(Movie).join(User).filter(
        Movie.id == Comment.movie_id, User.id == Comment.user_id).order_by(
        Comment.addtime.desc()).paginate(page=page, per_page=3)
    return render_template("admin/comment_list.html", page_data=page_data)


# 删除评论，并确保删除后留在当前页面（而不是每次删除后自动跳转回第一页）
@admin.route("/comment/del/<int:id>/<int:page>/", methods=['GET'])
@admin_login_required
# @admin_auth
def comment_del(id=None, page=None):
    comment = Comment.query.filter_by(id=id).first_or_404()
    db.session.delete(comment)
    db.session.commit()

    flash('删除评论成功!', 'ok')

    return redirect(url_for('admin.comment_list', page=page))


# 电影收藏列表
@admin.route("/moviecol/list/<int:page>/", methods=["GET"])
@admin_login_required
# @admin_auth
def moviecol_list(page=None):
    if page is None:
        page = 1
    page_data = Moviecol.query.join(Movie).join(User).filter(
        Movie.id == Moviecol.movie_id, User.id == Moviecol.user_id).order_by(
        Moviecol.addtime.desc()).paginate(page=page, per_page=3)
    return render_template("admin/moviecol_list.html", page_data=page_data)


# 删除收藏，并确保删除后留在当前页面（而不是每次删除后自动跳转回第一页）
@admin.route("/moviecol/del/<int:id>/<int:page>/", methods=['GET'])
@admin_login_required
# @admin_auth
def moviecol_del(id=None, page=None):
    moviecol = Moviecol.query.filter_by(id=id).first_or_404()
    db.session.delete(moviecol)
    db.session.commit()

    flash('删除电影收藏成功!', 'ok')

    return redirect(url_for('admin.moviecol_list', page=page))


# 操作日志列表
@admin.route("/oplog/list/<int:page>/", methods=["GET"])
@admin_login_required
# @admin_auth
def oplog_list(page=None):
    if page is None:
        page = 1
    page_data = Oplog.query.join(Admin).filter(
        Admin.id == Oplog.admin_id).order_by(
        Oplog.addtime.desc()).paginate(page=page, per_page=3)
    return render_template("admin/oplog_list.html", page_data=page_data)


# 管理员登录日志列表
@admin.route("/adminloginlog/list/<int:page>/", methods=["GET"])
@admin_login_required
# @admin_auth
def adminloginlog_list(page=None):
    if page is None:
        page = 1
    page_data = Adminlog.query.join(Admin).filter(
        Admin.id == Adminlog.admin_id).order_by(
        Adminlog.addtime.desc()).paginate(page=page, per_page=3)
    return render_template("admin/adminloginlog_list.html", page_data=page_data)


# 会员登录日志列表
@admin.route("/userloginlog/list/<int:page>/", methods=["GET"])
@admin_login_required
# @admin_auth
def userloginlog_list(page=None):
    if page is None:
        page = 1
    page_data = Userlog.query.join(User).filter(
        User.id == Userlog.user_id).order_by(
        Userlog.addtime.desc()).paginate(page=page, per_page=3)
    return render_template("admin/userloginlog_list.html", page_data=page_data)



# 添加权限
@admin.route("/auth/add/", methods=["GET", "POST"])
@admin_login_required
# @admin_auth
def auth_add():
    form = AuthForm()
    if form.validate_on_submit():
        data = form.data
        auth = Auth(name=data.get('name'), url=data.get('url'))
        db.session.add(auth)
        db.session.commit()
        flash("添加权限成功！", "ok")

        return redirect(url_for('admin.auth_add'))
    return render_template("admin/auth_add.html", form=form)


# 权限列表
@admin.route("/auth/list/<int:page>/", methods=["GET"])
@admin_login_required
# @admin_auth
def auth_list(page=None):
    if page is None:
        page = 1
    page_data = Auth.query.order_by(
        Auth.addtime.desc()).paginate(page=page, per_page=3)
    return render_template("admin/auth_list.html", page_data=page_data)


# 删除权限，并确保删除后留在当前页面（而不是每次删除后自动跳转回第一页）
@admin.route("/auth/del/<int:id>/<int:page>/", methods=['GET'])
@admin_login_required
def auth_del(id=None, page=None):
    auth = Auth.query.filter_by(id=id).first_or_404()
    db.session.delete(auth)
    db.session.commit()
    flash('删除权限成功!', 'ok')

    return redirect(url_for('admin.auth_list', page=page))


# 修改权限
@admin.route("/auth/edit/<int:id>/", methods=["GET", "POST"])
@admin_login_required
# @admin_auth
def auth_edit(id):
    form = AuthForm()
    auth = Auth.query.get_or_404(int(id))

    if form.validate_on_submit():
        data = form.data
        auth_count = Auth.query.filter_by(name=data.get('name')).count()
        if auth.name != data.get('name') and auth_count == 1:
            flash("权限名称已存在！", "err")
            return redirect(url_for('admin.auth_edit', id=id))
        auth.name = data.get('name')
        auth.url = data.get('url')
        db.session.add(auth)
        db.session.commit()
        flash("修改权限成功！", "ok")

        return redirect(url_for('admin.auth_edit', id=id))
    return render_template("admin/auth_edit.html", form=form, auth=auth)


# 添加角色
@admin.route("/role/add/", methods=["GET", "POST"])
@admin_login_required
# @admin_auth
def role_add():
    form = RoleForm()

    # 添加/删除权限的标签后，实时更新到"添加角色"的权限下拉列表中
    form.auths.choices = [(v.id, v.name) for v in Auth.query.all()]

    if form.validate_on_submit():
        data = form.data
        print("1st form.data: ", form.data)
        role = Role(
            name = data.get('name'),
            auths = ",".join(map(lambda v:str(v), data.get('auths')))   #map接收一个函数f和一个list，并通过把函数 f
        )                                                               #依次作用在 list 的每个元素上，得到一个新的 list 并返回
        db.session.add(role)
        db.session.commit()
        flash("添加角色成功！", "ok")
        return redirect(url_for('admin.role_add'))
    # else:
    #     print("2nd form.data: ", form.data)
    #     form.data
    return render_template("admin/role_add.html", form=form)


# 角色列表
@admin.route("/role/list/<int:page>/", methods=["GET"])
@admin_login_required
# @admin_auth
def role_list(page=None):
    if page is None:
        page = 1
    page_data = Role.query.order_by(
        Role.addtime.desc()).paginate(page=page, per_page=3)
    return render_template("admin/role_list.html", page_data=page_data)


# 删除角色，并确保删除后留在当前页面（而不是每次删除后自动跳转回第一页）
@admin.route("/role/del/<int:id>/<int:page>/", methods=['GET'])
@admin_login_required
# @admin_auth
def role_del(id=None, page=None):
    role = Role.query.filter_by(id=id).first_or_404()
    db.session.delete(role)
    db.session.commit()
    flash('删除角色成功!', 'ok')

    return redirect(url_for('admin.role_list', page=page))


# 修改角色
@admin.route("/role/edit/<int:id>/", methods=["GET", "POST"])
@admin_login_required
# @admin_auth
def role_edit(id):
    form = RoleForm()
    role = Role.query.get_or_404(int(id))

    # 添加/删除权限的标签后，实时更新到"修改角色"的权限下拉列表中
    form.auths.choices = [(v.id, v.name) for v in Auth.query.all()]
    # 如果当前权限列表为空，则提示
    if len(form.auths.choices) == 0:
        flash("当前权限列表为空，请先添加权限，再编辑角色！", "err")
        return redirect(url_for('admin.role_list', page=1))

    #由于auths在页面中是个多选框，没办法在role_edit.html中赋值，因此提前获取并赋值给表单
    if request.method == "GET":
        form.auths.data = list(map(lambda v:int(v), (role.auths).split(",")))

    # if form.validate_on_submit():   #如果用这个判断，form.validate_on_submit() 返回False，目前无解
    if request.method == "POST" and form.data['name'] != "" and len(form.data['auths']) != 0:
        data = form.data
        role_count = Role.query.filter_by(name=data.get('name')).count()
        if role.name != data.get('name') and role_count == 1:
            flash("角色名称已存在！", "err")
            return redirect(url_for('admin.auth_edit', id=id))
        role.name = data.get('name')
        role.auths = ",".join(map(lambda v:str(v), data.get('auths')))
        db.session.add(role)
        db.session.commit()
        flash("修改权限成功！", "ok")

        return redirect(url_for('admin.role_edit', id=id))
    return render_template("admin/role_edit.html", form=form, role=role)


# 添加管理员
@admin.route("/admin/add/", methods=["GET", "POST"])
@admin_login_required
# @admin_auth
def admin_add():
    from werkzeug.security import generate_password_hash
    form = AdminForm()

    # # 添加/删除角色后，实时更新到"所属角色"的下拉列表中
    form.role_id.choices = [(v.id, v.name) for v in Role.query.all()]

    if form.validate_on_submit():
        data = form.data
        print(data)
        admin = Admin(
            name = data.get('name'),
            pwd=generate_password_hash(data.get('repwd')),
            role_id = data.get('role_id'),
            is_super = 0
        )

        db.session.add(admin)
        db.session.commit()
        flash("添加管理员成功！", "ok")
        return redirect(url_for('admin.admin_add'))
    return render_template("admin/admin_add.html", form=form)


# 管理员列表
@admin.route("/admin/list/<int:page>/", methods=["GET"])
@admin_login_required
# @admin_auth
def admin_list(page=None):
    if page is None:
        page = 0
    page_data = Admin.query.join(Role).filter(Admin.role_id == Role.id).order_by(
        Admin.addtime.desc()).paginate(page=page, per_page=3)
    return render_template("admin/admin_list.html", page_data=page_data)


# 删除管理员，并确保删除后留在当前页面（而不是每次删除后自动跳转回第一页）
@admin.route("/admin/del/<int:id>/<int:page>/", methods=['GET'])
@admin_login_required
# @admin_auth
def admin_del(id=None, page=None):
    admin = Admin.query.filter_by(id=id).first_or_404()
    db.session.delete(admin)
    db.session.commit()
    flash('删除管理员成功!', 'ok')

    return redirect(url_for('admin.admin_list', page=page))