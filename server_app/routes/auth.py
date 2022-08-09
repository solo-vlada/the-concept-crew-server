from re import A
from flask import Blueprint, jsonify, make_response, request, current_app as app, redirect
from werkzeug.security import generate_password_hash,check_password_hash
from sqlalchemy import or_
from functools import wraps
import jwt
import datetime
from ..database.db import db
from ..models.tables import User, Messages

auth_routes = Blueprint("auth", __name__)

# Creates a decorator for checking valid json web tokens that can be used to limit methods to valid token users
def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        token = None
        if 'x-access-tokens' in request.headers:
            token = request.headers['x-access-tokens']

        if not token:
            return jsonify({'message': 'a valid token is missing'})
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(id=data['id']).first()
        except:
            return jsonify({'message': 'token is invalid'})
        return f(current_user, *args, **kwargs)
    return decorator

# Register new user / expects json post handled by frontend
@auth_routes.route('/register', methods=['POST'])
def register_user(): 
    try:
        content = request.json
        hashed_password = generate_password_hash(content['password'], method='sha256')

        new_user = User(
            username=content['username'], 
            password=hashed_password, 
            location=content['location'], 
            email=content['email']
        )

        db.session.add(new_user)
        db.session.commit()   
        return jsonify({'message': 'registered successfully'}), 201
    except:
        return jsonify({'message': 'registration unsuccessful'}), 400

# Login to existing account / expects basic auth containing the username and password
@auth_routes.route('/login', methods=['POST']) 
def login_user():

    # Check that login request was sent with basic auth
    auth = request.authorization  
    if not auth or not auth.username or not auth.password: 
        return make_response('could not verify basic auth', 401, {'Authentication': 'login required"'})   
    
    user = User.query.filter_by(username=auth.username).first()  
    if check_password_hash(user.password, auth.password):
    # if user.password == auth.password:
        token = jwt.encode({'id': user.id, 'username': user.username, 'exp' : datetime.datetime.utcnow() + datetime.timedelta(minutes=45)}, app.config['SECRET_KEY'], "HS256")

        return jsonify({'token': token}), 200
     
    return jsonify('could not verify'), 401

# Test route reciive all users in json format
@auth_routes.route('/users', methods=['GET'])
def get_all_users(): 
 
   users = User.query.all()
   result = []  
   for user in users:  
       user_data = {}  
       user_data['id'] = user.id 
       user_data['username'] = user.username
       user_data['password'] = user.password
       user_data['location'] = user.location
       user_data['email'] = user.email
     
       result.append(user_data)  
   return jsonify({'users': result})

@auth_routes.route('/msg/<int:user_id>', methods=['GET', 'POST'])
def messenger_handling(user_id):
    if request.method == 'GET':
        try:
            #  retrieve all messages sent by or too user
            all_messages = Messages.query.filter(Messages.sender == user_id and Messages.receiver == user_id )

            def message_serializer(message):
                return {
                    "message_text": message.message_text,
                    "sender": message.sender,
                    "receiver": message.receiver
                }
                
            return jsonify({'Messages': [*map(message_serializer, all_messages)]}), 200
        except:
            return jsonify({'Error': 'Cannot retrieve message\'s from non-existent user'}), 404
    else:
        try:
            # expect message in json format with user_id and receiver_id as the sender and recipient
            content = request.json
            new_message = Messages(
                message_text=content['message_text'],
                sender=content['user_id'],
                receiver=content['receiver_id']
            )

            db.session.add(new_message)
            db.session.commit()
            return jsonify({'Message sent': new_message.message_text}), 201
        except:
            return jsonify({'Error': 'Cannot send message to non-existent user'}), 404