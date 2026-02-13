from flask import Blueprint, jsonify, request, send_file
from auth import requires_auth
from datastore import get_user_by_id, get_user_by_sub, get_all_users
from google.cloud import datastore, storage
import requests
import os
import uuid
from io import BytesIO

users_bp = Blueprint("users", __name__)
datastore_client = datastore.Client()
storage_client = storage.Client()
bucket = storage_client.bucket(os.environ.get("CLOUD_STORAGE_BUCKET"))

@users_bp.route("/users/login", methods=["POST"])
def login():
    body = request.get_json()
    email = body.get("username")
    password = body.get("password")

    if not email or not password:
        return jsonify({"Error": "The request body is invalid"}), 400

    payload = {
        "grant_type": "http://auth0.com/oauth/grant-type/password-realm",
        "username": email,
        "password": password,
        "audience": os.environ.get("API_IDENTIFIER"),
        "client_id": os.environ.get("AUTH0_CLIENT_ID"),
        "client_secret": os.environ.get("AUTH0_CLIENT_SECRET"),
        "scope": "openid",
        "realm": "Username-Password-Authentication"
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_url = f"https://{os.environ.get('AUTH0_DOMAIN')}/oauth/token"

    response = requests.post(token_url, data=payload, headers=headers)

    if response.status_code != 200:
        return jsonify({"Error": "Unauthorized"}), 401

    token_data = response.json()
    return jsonify({"token": token_data.get("access_token")}), 200

@users_bp.route("/users/<int:user_id>", methods=["GET"])
@requires_auth
def get_user(user_id):
    requester = get_user_by_sub(request.user["sub"])
    if not requester:
        return jsonify({"Error": "Unauthorized"}), 401

    user_data = get_user_by_id(user_id)
    if not user_data:
        return jsonify({"Error": "Not found"}), 404

    if requester["role"] != "admin" and requester["sub"] != user_data["sub"]:
        return jsonify({"Error": "You don't have permission on this resource"}), 403

    response = {
        "id": user_id,
        "role": user_data["role"],
        "sub": user_data["sub"]
    }

    if "avatar" in user_data:
        response["avatar_url"] = f"{request.url_root}users/{user_id}/avatar"

    if user_data["role"] in ["student", "instructor"]:
        response["courses"] = []

    return jsonify(response), 200

@users_bp.route("/users", methods=["GET"])
@requires_auth
def get_all_users_handler():
    requester_info = get_user_by_sub(request.user["sub"])
    if not requester_info:
        return jsonify({"Error": "Unauthorized"}), 401

    if requester_info["role"] != "admin":
        return jsonify({"Error": "You don't have permission on this resource"}), 403

    return jsonify(get_all_users()), 200

@users_bp.route("/users/<int:user_id>/avatar", methods=["POST"])
@requires_auth
def upload_user_avatar(user_id):
    if not request.content_type or not request.content_type.startswith("multipart/form-data"):
        return jsonify({"Error": "The request body is invalid"}), 400
    
    file = request.files.get("file")
    if not file or file.filename.strip() == "":
        return jsonify({"Error": "The request body is invalid"}), 400

    requester = get_user_by_sub(request.user["sub"])
    user = get_user_by_id(user_id)

    if not requester or not user:
        return jsonify({"Error": "Unauthorized"}), 401

    if requester["sub"] != user["sub"]:
        return jsonify({"Error": "You don't have permission on this resource"}), 403

    filename = f"avatars/{user_id}_{uuid.uuid4().hex}.png"
    blob = bucket.blob(filename)
    blob.upload_from_file(file, content_type=file.content_type or "image/png")
    blob.make_public()

    key = datastore_client.key("users", user_id)
    entity = datastore_client.get(key)
    entity["avatar"] = filename
    datastore_client.put(entity)

    return jsonify({"avatar_url": f"{request.url_root}users/{user_id}/avatar"}), 200

@users_bp.route("/users/<int:user_id>/avatar", methods=["GET"])
@requires_auth
def get_user_avatar(user_id):
    requester = get_user_by_sub(request.user["sub"])
    user = get_user_by_id(user_id)

    if not requester or not user:
        return jsonify({"Error": "Unauthorized"}), 401

    if user["sub"] != requester["sub"]:
        return jsonify({"Error": "You don't have permission on this resource"}), 403

    if "avatar" not in user:
        return jsonify({"Error": "Not found"}), 404

    blob = bucket.blob(user["avatar"])
    if not blob.exists():
        return jsonify({"Error": "Not found"}), 404

    data = blob.download_as_bytes()
    return send_file(BytesIO(data), mimetype="image/png")

@users_bp.route("/users/<int:user_id>/avatar", methods=["DELETE"])
@requires_auth
def delete_user_avatar(user_id):
    requester = get_user_by_sub(request.user["sub"])
    user = get_user_by_id(user_id)

    if not requester or not user:
        return jsonify({"Error": "Unauthorized"}), 401

    if user["sub"] != requester["sub"]:
        return jsonify({"Error": "You don't have permission on this resource"}), 403

    if "avatar" not in user:
        return jsonify({"Error": "Not found"}), 404

    blob = bucket.blob(user["avatar"])
    blob.delete()

    key = datastore_client.key("users", user_id)
    entity = datastore_client.get(key)
    del entity["avatar"]
    datastore_client.put(entity)

    return "", 204
