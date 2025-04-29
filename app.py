# social_network.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from neo4j import GraphDatabase
from dataclasses import dataclass
from typing import List, Optional

from neo4j import GraphDatabase

import os

from dotenv import load_dotenv, dotenv_values 

load_dotenv() 


# ======================
# Database Access Layer
# ======================
from typing import List, Optional

class Database:
    URI = os.getenv("URI")
    AUTH = (os.getenv("USERNAME"), os.getenv("PASSWORD"))
    driver = GraphDatabase.driver(URI, auth=AUTH)

    def __init__(self):
        self._init_db()

    def _init_db(self):
        self.driver.execute_query(
            "CREATE CONSTRAINT unique_user_id IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE;",
            database_="neo4j"
        )
        self.driver.execute_query(
            "CREATE CONSTRAINT unique_username IF NOT EXISTS FOR (u:User) REQUIRE u.username IS UNIQUE;",
            database_="neo4j"
        )

    def create_user(self, user_id: str, username: str):
        self.driver.execute_query(
            """
            CREATE (u:User { user_id: $user_id, username: $username })
            """,
            parameters={"user_id": user_id, "username": username},
            database_="neo4j"
        )

    def get_all_users(self) -> List[dict]:
        result = self.driver.execute_query(
            """
            MATCH (u:User)
            RETURN u.user_id AS user_id, u.username AS username, id(u) AS id
            """,
            database_="neo4j"
        )[0]
        return [{"user": r["user_id"], "name": r["username"], "id": r["id"]} for r in result]

    def get_user(self, user_id: int) -> Optional[dict]:
        result = self.driver.execute_query(
            """
            MATCH (u:User)
            WHERE id(u) = """ + str(user_id) + """
            RETURN u.user_id AS user_id, u.username AS username, id(u) AS id
            """,
            parameters={"id": user_id},
            database_="neo4j"
        )[0]
        if result:
            r = result[0]
            return {"user": r["user_id"], "name": r["username"], "id": r["id"]}
        return None

    def create_post(self, user_id: str, content: str) -> int:
        result = self.driver.execute_query(
            """
            MATCH (u:User {user_id: $user_id})
            CREATE (p:Post {content: $content, timestamp: timestamp()})
            SET p.user_id = $user_id
            CREATE (u)-[:POSTED]->(p)
            RETURN id(p) AS post_id
            """,
            parameters={"user_id": user_id, "content": content},
            database_="neo4j"
        )
        return result[0]["post_id"]

    def get_posts_by_user(self, user_id: int) -> List[dict]:
        result = self.driver.execute_query(
            """
            MATCH (u:User)-[:POSTED]->(p:Post)
            WHERE id(u) =  """ + str(user_id) + """
            RETURN p.content AS content, p.timestamp AS timestamp, u.username AS username
            ORDER BY p.timestamp DESC
            """,
            parameters={"id": user_id},
            database_="neo4j"
        )[0]
        return [{"content": r["content"], "timestamp": r["timestamp"], "username": r["username"]} for r in result]

    def get_feed(self, user_id: int) -> List[dict]:
        result = self.driver.execute_query(
            """
            MATCH (u:User)-[:FOLLOWS]->(f:User)-[:POSTED]->(p:Post)
            WHERE id(u) =  """ + str(user_id) + """
            RETURN p.content AS content, p.timestamp AS timestamp, f.username AS username
            ORDER BY p.timestamp DESC
            """,
            parameters={"id": user_id},
            database_="neo4j"
        )[0]
        return [{"content": r["content"], "timestamp": r["timestamp"], "username": r["username"]} for r in result]

    def follow_user(self, follower_id: int, followee_id: int) -> bool:
        result = self.driver.execute_query(
            """
            MATCH (f:User), (u:User)
            WHERE id(f) = $follower_id AND id(u) = $followee_id
            CREATE (f)-[:FOLLOWS]->(u)
            RETURN COUNT(*) AS relationship_created
            """,
            parameters={"follower_id": follower_id, "followee_id": followee_id},
            database_="neo4j"
        )
        return result[0]["relationship_created"] > 0

    def get_followers(self, user_id: int) -> List[dict]:
        result = self.driver.execute_query(
            """
            MATCH (f:User)-[:FOLLOWS]->(u:User)
            WHERE id(u) = """ + str(user_id) + """
            RETURN f.user_id AS user_id, f.username AS username
            """,
            parameters={"id": user_id},
            database_="neo4j"
        )[0]
        return [{"user": r["user_id"], "name": r["username"]} for r in result]

    def get_following(self, user_id: int) -> List[dict]:
        result = self.driver.execute_query(
            """
            MATCH (u:User)-[:FOLLOWS]->(f:User)
            WHERE id(u) =  """ + str(user_id) + """
            RETURN f.user_id AS user_id, f.username AS username
            """,
            parameters={"id": user_id},
            database_="neo4j"
        )[0]
        return [{"user": r["user_id"], "name": r["username"]} for r in result]

    def unfollow_user(self, follower_id: int, followee_id: int) -> bool:
        result = self.driver.execute_query(
            """
            MATCH (f:User)-[r:FOLLOWS]->(u:User)
            WHERE id(f) = $follower_id AND id(u) = $followee_id
            DELETE r
            RETURN COUNT(*) AS relationship_deleted
            """,
            parameters={"follower_id": follower_id, "followee_id": followee_id},
            database_="neo4j"
        )
        return result[0]["relationship_deleted"] > 0


# ======================
# Web Application
# ======================
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
db = Database()

# Sample data initialization
with app.app_context():
    # Create some sample users if they don't exist
    if not db.get_all_users():
        db.create_user('alice', 'Alice Smith')
        db.create_user('bob', 'Bob Johnson')
        db.create_user('charlie', 'Charlie Brown')

# ======================
# API Endpoints
# ======================
@app.route('/api/users', methods=['GET'])
def api_get_users():
    return jsonify(db.get_all_users())

@app.route('/api/users/<int:user_id>', methods=['GET'])
def api_get_user(user_id):
    user = db.get_user(user_id)
    return jsonify(user) if user else ('User not found', 404)

@app.route('/api/users/<int:user_id>/posts', methods=['GET'])
def api_get_user_posts(user_id):
    return jsonify(db.get_posts_by_user(user_id))

@app.route('/api/users/<int:user_id>/feed', methods=['GET'])
def api_get_user_feed(user_id):
    return jsonify(db.get_feed(user_id))

@app.route('/api/users/<int:user_id>/followers', methods=['GET'])
def api_get_user_followers(user_id):
    return jsonify(db.get_followers(user_id))

@app.route('/api/users/<int:user_id>/following', methods=['GET'])
def api_get_user_following(user_id):
    return jsonify(db.get_following(user_id))

@app.route('/api/posts', methods=['POST'])
def api_create_post():
    data = request.get_json()
    post_id = db.create_post(data['user_id'], data['content'])
    return jsonify({'post_id': post_id}), 201

@app.route('/api/follow', methods=['POST'])
def api_follow_user():
    data = request.get_json()
    success = db.follow_user(data['follower_id'], data['followee_id'])
    return jsonify({'success': success}), 201 if success else 200

# ======================
# Frontend Routes
# ======================
@app.route('/')
def home():
    users = db.get_all_users()
    current_user = None
    if 'user_id' in session:
        current_user = db.get_user(session['user_id'])
    
    return render_template('index.html', users=users, current_user=current_user)

@app.route('/user/<int:user_id>')
def user_profile(user_id):
    user = db.get_user(user_id)
    if not user:
        return "User not found", 404
        
    current_user = None
    is_following = False
    
    if 'user_id' in session:
        current_user = db.get_user(session['user_id'])
        if current_user and current_user['id'] != user_id:
            # Check if current user is following this profile user
            following = db.get_following(current_user['id'])
            is_following = any(f['id'] == user_id for f in following)
    
    posts = db.get_posts_by_user(user_id)
    followers = db.get_followers(user_id)
    following = db.get_following(user_id)

    
    return render_template('profile.html', 
                         user=user, 
                         posts=posts,
                         followers=followers,
                         following=following,
                         current_user=current_user,
                         is_following=is_following)

@app.route('/user/<int:user_id>/feed')
def user_feed(user_id):
    user = db.get_user(user_id)
    feed = db.get_feed(user_id)
    return render_template('feed.html', user=user, feed=feed)

@app.route('/create_post', methods=['POST'])
def create_post():
    user_id = int(request.form['user_id'])
    content = request.form['content']
    db.create_post(user_id, content)
    return redirect(url_for('user_profile', user_id=user_id))

@app.route('/login/<int:user_id>')
def login(user_id):
    session['user_id'] = user_id
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

@app.route('/follow', methods=['POST'])
def follow():
    follower_id = int(request.form['follower_id'])
    followee_id = int(request.form['followee_id'])
    
    # Check if the user is already following
    following = db.get_following(follower_id)
    is_following = any(f['id'] == followee_id for f in following)
    
    if is_following:
        # Implement unfollow functionality (you'll need to add this to your Database class)
        db.unfollow_user(follower_id, followee_id)
    else:
        db.follow_user(follower_id, followee_id)
    
    return redirect(url_for('user_profile', user_id=followee_id))

# ======================
# HTML Templates
# ======================
@app.route('/templates/<template_name>')
def serve_template(template_name):
    return render_template(template_name)

# Template rendering functions
app.jinja_env.globals.update(
    render_index=lambda: render_template('index.html', users=db.get_all_users()),
    render_profile=lambda user_id: render_template(
        'profile.html',
        user=db.get_user(user_id),
        posts=db.get_posts_by_user(user_id),
        followers=db.get_followers(user_id),
        following=db.get_following(user_id)
    )
)

if __name__ == '__main__':
    app.run(debug=True)