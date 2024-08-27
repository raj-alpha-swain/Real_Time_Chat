from flask import Flask, redirect, request, url_for, session, render_template, jsonify
from flask_socketio import SocketIO, join_room, leave_room, send
from werkzeug.utils import secure_filename
import os
import random
from string import ascii_letters

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sfsndfkjn'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
socketio = SocketIO(app)

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def generatecode(length: int, existing_codes: list[str]) -> str:
    while True:
        code = ''.join(random.choice(ascii_letters) for i in range(length))
        if code not in existing_codes:
            return code

rooms = {}

@app.route("/", methods=['GET', "POST"])
def home():
    session.clear()

    if request.method == "POST":
        name = request.form.get("name")
        create = request.form.get("create", False)
        code = request.form.get("code")
        join = request.form.get("join", False)

        if not name:
            return render_template('home.html', error="Name is required", code=code)

        if create != False:
            room_code = generatecode(6, list(rooms.keys()))
            new_room = {
                'members': 0,
                'messages': []
            }
            rooms[room_code] = new_room
        if join != False:
            if not code:
                return render_template('home.html', error="Please enter a room code to enter a chat room", name=name)
            if code not in rooms:
                return render_template('home.html', error="Room code not found", name=name)

            room_code = code

        session['room'] = room_code
        session['name'] = name
        return redirect(url_for('room'))
    else:
        return render_template('home.html')

@app.route('/room')
def room():
    name = session.get('name')
    room = session.get('room')

    if name is None or room is None or room not in rooms:
        return redirect(url_for('home'))
    messages = rooms[room]['messages']
    return render_template('room.html', user=name, room=room, messages=messages)

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image part'})
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    url = url_for('static', filename='uploads/' + filename)
    return jsonify({'success': True, 'url': url})

@socketio.on('connect')
def handle_connect():
    name = session.get('name')
    room = session.get('room')

    if name is None or room is None:
        return
    if room not in rooms:
        leave_room(room)

    join_room(room)
    send({
        "sender": "",
        "message": f"{name} has entered the chat"
    }, to=room)
    rooms[room]["members"] += 1

@socketio.on('message')
def handle_message(payload):
    room = session.get('room')
    name = session.get('name')

    if room not in rooms:
        return

    message = {
        "sender": name,
        "message": payload["message"]
    }
    send(message, to=room)
    rooms[room]["messages"].append(message)

@socketio.on('image')
def handle_image(payload):
    room = session.get('room')
    name = session.get('name')

    if room not in rooms:
        return

    image_message = {
        "sender": name,
        "url": payload["url"]
    }
    send(image_message, to=room)
    rooms[room]["messages"].append(image_message)

@socketio.on('disconnect')
def handle_disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]

    send({
        "message": f"{name} has left the chat",
        "sender": ""
    }, to=room)

if __name__ == "__main__":
    socketio.run(app, debug=True)
