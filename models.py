from flask_mongoengine import MongoEngine

db = MongoEngine()
class User(db.Document):
    username = db.StringField(required=True, unique=True)
    email = db.EmailField(required=True, unique=True)
    password = db.StringField(required=True)
    verified = db.BooleanField(default=False)
    email = db.EmailField()(required=True, unique=True)
    verification_token = db.StringField()

class DiabetesData(db.Document):
    user = db.ReferenceField(User)
    preg_count = db.IntField(required=True)
    glucose = db.IntField(required=True)
    blood_pressure = db.IntField(required=True)
    skin_thickness = db.IntField(required=True)
    insulin = db.FloatField(required=True)
    bmi = db.FloatField(required=True)
    diabetes_function = db.FloatField(required=True)
    age = db.IntField(required=True)
    diagnosis = db.StringField(required=True)
