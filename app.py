from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import lru_cache

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key'
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

@lru_cache(maxsize=1)
def get_cached_employees():
    return Employee.query.all()

@app.route('/')
@login_required
def index():
    employees = get_cached_employees()
    open_works = {e.id: WorkTime.query.filter_by(employee_id=e.id, end_time=None).first() for e in employees}
    return render_template('index.html', employees=employees, open_works=open_works)

@app.route('/employee/add', methods=['POST'])
@login_required
def add_employee():
    full_name = request.form.get('full_name')
    hourly_rate = request.form.get('hourly_rate')
    try:
        hourly_rate = float(hourly_rate)
    except:
        hourly_rate = 0
    if full_name and hourly_rate > 0:
        db.session.add(Employee(full_name=full_name, hourly_rate=hourly_rate))
        db.session.commit()
        get_cached_employees.cache_clear()
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
    get_cached_employees.cache_clear()
    flash('Сотрудник удалён')
    return redirect(url_for('index'))

@app.route('/work/start/<int:employee_id>')
@login_required
def start_work(employee_id):
    open_work = WorkTime.query.filter_by(employee_id=employee_id, end_time=None).first()
    if open_work:
        flash('Смена уже начата')
    else:
        db.session.add(WorkTime(employee_id=employee_id, start_time=datetime.now()))
        db.session.commit()
        flash('Смена начата')
    return redirect(url_for('index'))

@app.route('/work/end/<int:worktime_id>')
@login_required
def end_work(worktime_id):
    wt = WorkTime.query.get_or_404(worktime_id)
    if wt.end_time is None:
        wt.end_time = datetime.now()
        db.session.commit()
        flash('Смена завершена')
    else:
        flash('Смена уже завершена')
    return redirect(url_for('index'))

@app.route('/salary/<int:employee_id>')
@login_required
def salary(employee_id):
    emp = Employee.query.get_or_404(employee_id)
    times = WorkTime.query.filter_by(employee_id=employee_id).filter(WorkTime.end_time.isnot(None)).all()
    total_hours = sum([(w.end_time - w.start_time).total_seconds() for w in times]) / 3600
    return render_template('salary.html', employee=emp, hours=total_hours, total_pay=total_hours * emp.hourly_rate)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin')
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)
