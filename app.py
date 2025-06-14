from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True)
    password_hash = db.Column(db.String(150))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    hourly_rate = db.Column(db.Float, nullable=False)
    worktimes = db.relationship('WorkTime', backref='employee', lazy=True, cascade="all, delete-orphan")

class WorkTime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Неверный логин или пароль')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    employees = Employee.query.all()
    open_works = {}
    for emp in employees:
        open_work = WorkTime.query.filter_by(employee_id=emp.id, end_time=None).first()
        open_works[emp.id] = open_work
    return render_template('index.html', employees=employees, open_works=open_works)

@app.route('/employee/add', methods=['POST'])
@login_required
def add_employee():
    full_name = request.form.get('full_name')
    hourly_rate = request.form.get('hourly_rate')
    try:
        hourly_rate = float(hourly_rate)
    except (ValueError, TypeError):
        hourly_rate = 0
    if full_name and hourly_rate > 0:
        emp = Employee(full_name=full_name, hourly_rate=hourly_rate)
        db.session.add(emp)
        db.session.commit()
        flash('Сотрудник добавлен')
    else:
        flash('Неверные данные')
    return redirect(url_for('index'))

@app.route('/employee/delete/<int:employee_id>', methods=['POST'])
@login_required
def delete_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    db.session.delete(employee)
    db.session.commit()
    flash(f"Сотрудник '{employee.full_name}' удалён")
    return redirect(url_for('index'))

@app.route('/work/start/<int:employee_id>', methods=['GET'])
@login_required
def start_work(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    open_work = WorkTime.query.filter_by(employee_id=employee.id, end_time=None).first()
    if open_work:
        flash('Смена уже начата')
    else:
        new_work = WorkTime(employee_id=employee.id, start_time=datetime.now())
        db.session.add(new_work)
        db.session.commit()
        flash(f'Смена для {employee.full_name} начата')
    return redirect(url_for('index'))

@app.route('/work/end/<int:worktime_id>', methods=['GET'])
@login_required
def end_work(worktime_id):
    worktime = WorkTime.query.get_or_404(worktime_id)
    if worktime.end_time is None:
        worktime.end_time = datetime.now()
        db.session.commit()
        flash('Смена завершена')
    else:
        flash('Смена уже завершена')
    return redirect(url_for('index'))

@app.route('/salary/<int:employee_id>')
@login_required
def salary(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    worktimes = WorkTime.query.filter_by(employee_id=employee.id).filter(WorkTime.end_time.isnot(None)).all()
    total_seconds = sum([(wt.end_time - wt.start_time).total_seconds() for wt in worktimes])
    hours = total_seconds / 3600
    total_pay = hours * employee.hourly_rate
    return render_template('salary.html', employee=employee, hours=hours, total_pay=total_pay)

# Автоинициализация базы данных при запуске
with app.app_context():
    db.create_all()

    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin')
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()
        print("Admin user created.")
    else:
        print("Admin user already exists.")
