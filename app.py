from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import pickle
import datetime
import uuid
from bson import ObjectId
from pymongo import DESCENDING
from dotenv import load_dotenv
import os


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config["MONGO_URI"] = os.getenv("MONGO_URI")

# Flask-Mail configuration
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = os.getenv("MAIL_PORT")
app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS")
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

# print(app.config)
# print(app.config["MAIL_USERNAME"])
# print(app.config["MAIL_PASSWORD"])
# print(app.config["MAIL_USE_TLS"])
# print(app.config["MAIL_PORT"])
# print(app.config["MAIL_SERVER"])
# print(app.config["MONGO_URI"])

mail = Mail(app)

mongo = PyMongo(app)

# Load scaler and ML model
scaler = pickle.load(open("Model/standardScalar.pkl", "rb"))
model = pickle.load(open("Model/modelForPrediction.pkl", "rb"))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = mongo.db.users
        existing_user = users.find_one({'username': request.form['username']})
        if existing_user is None:
            hashed_password = generate_password_hash(request.form['password'])
            verification_token = str(uuid.uuid4())
            users.insert_one({
                'username': request.form['username'],
                'password': hashed_password,
                'verified': False,
                'email': request.form['email'],
                'verification_token': verification_token
            })
            session['user'] = request.form['username']
            
            # Send verification email
            msg = Message('Email Verification', sender=os.getenv("MAIL_USERNAME"), recipients=[request.form['email']])
            msg.body = f"Please click the link to verify your email: {url_for('verify_email', token=verification_token, _external=True)}"
            mail.send(msg)
            
            flash('Registration successful! Please check your email to verify your account.', 'success')
            return redirect(url_for('login'))
        flash('That username already exists!', 'error')
    return render_template('register.html')

@app.route('/verify_email/<token>')
def verify_email(token):
    users = mongo.db.users
    user = users.find_one({'verification_token': token})
    if user:
        users.update_one({'_id': user['_id']}, {'$set': {'verified': True}})
        flash('Email verification successful! You can now log in.', 'success')
        return redirect(url_for('login'))
    flash('Invalid or expired token.', 'error')
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = mongo.db.users
        login_user = users.find_one({'username': request.form['username']})

        if login_user and check_password_hash(login_user['password'], request.form['password']):
            if login_user['verified']:
                session['user'] = request.form['username']
                flash('Login successful!', 'success')
                return redirect(url_for('profile'))
            else:
                flash('Account not verified. Please check your email.', 'error')
                return redirect(url_for('login'))

        flash('Invalid username/password combination', 'error')

    return render_template('login.html')

@app.route('/profile')
def profile():
    if 'user' in session:
        user = session['user']
        results = mongo.db.results.find({'username': user}).sort('date', DESCENDING)
        return render_template('profile.html', user=user, results=results)
    flash('You need to log in to view this page.', 'error')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if 'user' in session:
        if request.method == 'POST':
            preg = int(request.form.get('pregs'))
            gluc = int(request.form.get('gluc'))
            bp = int(request.form.get('bp'))
            skin = int(request.form.get('skin'))
            insulin = float(request.form.get('insulin'))
            bmi = float(request.form.get('bmi'))
            func = float(request.form.get('func'))
            age = int(request.form.get('age'))

            input_features = [[preg, gluc, bp, skin, insulin, bmi, func, age]]
            input_features_scaled = scaler.transform(input_features)
            prediction = model.predict(input_features_scaled)[0]

            # Convert numpy.int64 to native Python int
            prediction = int(prediction)

            # Save the prediction result to the database
            result_id = mongo.db.results.insert_one({
                'username': session['user'],
                'date': datetime.datetime.now(),
                'preg': preg,
                'gluc': gluc,
                'bp': bp,
                'skin': skin,
                'insulin': insulin,
                'bmi': bmi,
                'func': func,
                'age': age,
                'prediction': prediction
            }).inserted_id

            # Send the diabetes report to the user
            user_name = session['user']
            email = mongo.db.users.find_one({'username': user_name})['email']
            msg = Message('Diabetes Report', sender=os.getenv("MAIL_USERNAME"), recipients=[email])
            msg.body = f"Here is your diabetes prediction report:\n\n" \
                       f"Pregnancies: {preg}\n" \
                       f"Glucose: {gluc}\n" \
                       f"Blood Pressure: {bp}\n" \
                       f"Skin Thickness: {skin}\n" \
                       f"Insulin: {insulin}\n" \
                       f"BMI: {bmi}\n" \
                       f"Diabetes Pedigree Function: {func}\n" \
                       f"Age: {age}\n" \
                       f"Prediction: {'Diabetic' if prediction == 1 else 'Not Diabetic'}\n\n" \
                       f"Thank you for using our service."
            mail.send(msg)
            
            return render_template('prediction.html', prediction=prediction)
        return render_template('predict.html')
    flash('You need to log in to use this feature.', 'error')
    return redirect(url_for('login'))


@app.route('/delete_record/<record_id>', methods=['POST'])
def delete_record(record_id):
    if 'user' in session:
        mongo.db.results.delete_one({'_id': ObjectId(record_id), 'username': session['user']})
        flash('Record deleted successfully!', 'success')
        return redirect(url_for('profile'))
    flash('You need to log in to perform this action.', 'error')
    return redirect(url_for('login'))

@app.route('/delete_all_records', methods=['POST'])
def delete_all_records():
    if 'user' in session:
        mongo.db.results.delete_many({'username': session['user']})
        flash('All records deleted successfully!', 'success')
        return redirect(url_for('profile'))
    flash('You need to log in to perform this action.', 'error')
    return redirect(url_for('login'))

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True ,port=int(os.getenv('PORT', 8080)))
