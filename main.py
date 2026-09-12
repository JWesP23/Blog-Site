from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, user_logged_in
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreatePostForm, CreateUserForm, LoginUserForm, CommentForm
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///Blog_Content.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)

#initiate flask login manager
login_manager = LoginManager()
login_manager.init_app(app)

#initialize gravatar for commenter avatars
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=True,
                    base_url=None)


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    # Create reference to the User object. The "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="posts")

    #The "comment_" refers to the author property in the Comment class.
    comments = relationship("Comment", back_populates="parent_post")


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(250), nullable=False)
    user_name: Mapped[str] = mapped_column(String(250), nullable=False)

    #The "comment_" refers to the author property in the Comment class.
    comments = relationship("Comment", back_populates="comment_author")

    #The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")

    #Currently, only "ADMIN", and "USER" supported
    access: Mapped[str] = mapped_column(String(250), nullable=True)


class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    # Create reference to the User object. The "posts" refers to the posts property in the User class.
    comment_author = relationship("User", back_populates="comments")

    post_id: Mapped[str] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")


with app.app_context():
    db.create_all()


#returns True if the current logged-in User is an admin
def is_user_admin():
    if current_user.is_anonymous or not current_user.is_authenticated:
        return False
    elif current_user.access == "ADMIN":
        return True
    else:
        return False


#restricts routes that should not be accessible to users so that they cannot access certain pages just by typing in the correct urls
def admin_only(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if is_user_admin():
            return function(*args, **kwargs)
        else:
            return abort(403)

    return decorated_function


#required by flask login manager
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, ident= int(user_id))


@app.route('/register', methods= ["GET", "POST"])
def register():

    form = CreateUserForm()

    if form.validate_on_submit():

        #check if account already exists
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if user:
            # User already exists
            flash("There's already an account signed up with that email, Please log in instead.")
            return redirect(url_for('login'))


        hashed_password = generate_password_hash(password= str(form.password.data), method= 'pbkdf2:sha256', salt_length= 8)
        new_user = User(
            email= form.email.data, # type: ignore
            password= hashed_password, # type: ignore
            user_name= form.user_name.data, # type: ignore
            access= "USER" # type: ignore
        )

        #append users DB
        db.session.add(new_user)
        db.session.commit()

        #log the user in
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        login_user(user)

        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form= form)


@app.route('/login', methods= ["GET", "POST"])
def login():

    form = LoginUserForm()

    if request.method == "POST":
        if form.validate_on_submit():

            #check if account exists
            user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
            if not user:
                # User doesn't exist
                flash("There's no account signed up with that email, Please make sure the email you entered is correct or register a new account instead.")
            elif not check_password_hash(password= str(form.password.data), pwhash= user.password):
                flash("Email/Password is incorrect, please check for errors and try again.")
            else:
                login_user(user)
                return redirect(url_for("get_all_posts"))

    return render_template("login.html", form= form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, is_admin= is_user_admin())


@app.route("/post/<int:post_id>", methods= ["POST", "GET"])
def show_post(post_id):
    form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)

    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("You must be logged in to leave a comment.")

        elif form.validate_on_submit():
            new_comment = Comment(
                text= form.comment_text.data, # type: ignore
                comment_author= current_user, # type: ignore
                parent_post= requested_post # type: ignore
            )

            #don't accept empty comments
            if new_comment.text.strip() != "":
                db.session.add(new_comment)
                db.session.commit()

            form.comment_text.data = ""

    return render_template("post.html", post=requested_post, is_admin= is_user_admin(), form= form)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data, # type: ignore
            subtitle=form.subtitle.data, # type: ignore
            body=form.body.data, # type: ignore
            img_url=form.img_url.data, # type: ignore
            author=current_user, # type: ignore
            date=date.today().strftime("%B %d, %Y") # type: ignore
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )

    if edit_form.validate_on_submit():
        post.title = edit_form.title.data # type: ignore
        post.subtitle = edit_form.subtitle.data # type: ignore
        post.img_url = edit_form.img_url.data # type: ignore
        post.author = current_user # type: ignore
        post.body = edit_form.body.data # type: ignore
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False, port=5002)

