from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import boto3
from botocore.exceptions import ClientError
import json

app = Flask(__name__)
CORS(app)

# Use this code snippet in your app.
# If you need more information about configurations
# or implementing the sample code, visit the AWS docs:
# https://aws.amazon.com/developer/language/python/

def get_secret():
    secret_name = "rds!db-fd78b098-1ded-4aff-86cc-6cf13e3042c3"
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise e

    # SecretsManager may return a JSON string or plain string/binary
    if 'SecretString' in get_secret_value_response:
        secret_string = get_secret_value_response['SecretString']
        try:
            return json.loads(secret_string)
        except json.JSONDecodeError:
            return {'password': secret_string}
    else:
        secret_binary = get_secret_value_response.get('SecretBinary')
        if secret_binary:
            try:
                decoded = secret_binary.decode('utf-8')
            except Exception:
                decoded = str(secret_binary)
            try:
                return json.loads(decoded)
            except json.JSONDecodeError:
                return {'password': decoded}
    return {}


# Load DB credentials from AWS Secrets Manager (required)
_secret = get_secret()
if not _secret:
    raise RuntimeError('Database secret not found in AWS Secrets Manager')

host = _secret.get('host')
user = _secret.get('username') or _secret.get('user')
password = _secret.get('password')
database = _secret.get('dbname') or _secret.get('database')

missing = [k for k,v in (('host', host), ('user', user), ('password', password), ('database', database)) if not v]
if missing:
    raise RuntimeError(f"Missing DB fields in secret: {', '.join([m[0] for m in [(k,v) for k,v in (('host', host), ('user', user), ('password', password), ('database', database))] if not m[1]])}")

db_config = {
    'host': host,
    'user': user,
    'password': password,
    'database': database
}

# Connect to MySQL
def get_db_connection():
    return mysql.connector.connect(**db_config)

# 1️⃣ Get all users
@app.route('/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(users)

# 2️⃣ Get user by ID
@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return jsonify(user)
    return jsonify({'error': 'User not found'}), 404

# 3️⃣ Add a new user
@app.route('/users/add', methods=['POST'])
def add_user():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    if not name or not email:
        return jsonify({'error': 'Name and Email are required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email) VALUES (%s, %s)",
            (name, email)
        )
        conn.commit()
        return jsonify({'message': 'User added successfully'}), 201
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# 4️⃣ Update user by ID
@app.route('/users/update/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    name = data.get('name')
    email = data.get('email')
    if not name or not email:
        return jsonify({'error': 'Name and Email are required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'User not found'}), 404

    try:
        cursor.execute(
            "UPDATE users SET name = %s, email = %s WHERE id = %s",
            (name, email, user_id)
        )
        conn.commit()
        return jsonify({'message': 'User updated successfully'})
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# 5️⃣ Delete user by ID
@app.route('/users/delete/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'User not found'}), 404

    try:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return jsonify({'message': 'User deleted successfully'})
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# 🔹 Simple Hello route
@app.route('/')
def index():
    return "Hello"

# Entry Point
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
