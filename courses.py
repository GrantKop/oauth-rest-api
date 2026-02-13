from flask import Blueprint, jsonify, request
from auth import requires_auth
from datastore import get_user_by_sub, get_user_by_id
from google.cloud import datastore
import os

courses_bp = Blueprint("courses", __name__)
datastore_client = datastore.Client()

def error_response(message, code):
    return jsonify({"Error": message}), code

@courses_bp.route("/courses", methods=["POST"])
@requires_auth
def create_course():
    requester = get_user_by_sub(request.user["sub"])
    if not requester:
        return error_response("Unauthorized", 401)
    if requester["role"] != "admin":
        return error_response("You don't have permission on this resource", 403)

    data = request.get_json()
    required_fields = {"subject", "number", "title", "term", "instructor_id"}
    if not data or not required_fields.issubset(data.keys()):
        return error_response("The request body is invalid", 400)

    instructor = get_user_by_id(data["instructor_id"])
    if not instructor or instructor["role"] != "instructor":
        return error_response("The request body is invalid", 400)

    course = datastore.Entity(datastore_client.key("courses"))
    course.update({
        "subject": data["subject"],
        "number": data["number"],
        "title": data["title"],
        "term": data["term"],
        "instructor_id": data["instructor_id"],
        "students": []
    })
    datastore_client.put(course)

    return jsonify({
        "id": course.key.id,
        "subject": course["subject"],
        "number": course["number"],
        "title": course["title"],
        "term": course["term"],
        "instructor_id": course["instructor_id"],
        "self": build_course_url(str(course.key.id))
    }), 201

def build_course_url(course_id):
    return f"https://tarpaulin-app-assignment-6.wl.r.appspot.com/courses/{course_id}"

@courses_bp.route("/courses", methods=["GET"])
def list_courses():
    offset = int(request.args.get("offset", 0))
    limit = int(request.args.get("limit", 3))

    query = datastore_client.query(kind="courses")
    query.order = ["subject"]
    courses_iter = query.fetch(offset=offset, limit=limit)
    results = list(courses_iter)

    course_list = []
    for c in results:
        course_list.append({
            "id": c.key.id,
            "subject": c["subject"],
            "number": c["number"],
            "title": c["title"],
            "term": c["term"],
            "instructor_id": c["instructor_id"],
            "self": build_course_url(c.key.id)
        })

    response = {"courses": course_list}
    if len(course_list) == limit:
        response["next"] = f"https://tarpaulin-app-assignment-6.wl.r.appspot.com/courses?limit={limit}&offset={offset + limit}"
    return jsonify(response), 200

@courses_bp.route("/courses/<int:course_id>", methods=["GET"])
def get_course(course_id):
    key = datastore_client.key("courses", course_id)
    course = datastore_client.get(key)
    if not course:
        return error_response("Not found", 404)

    return jsonify({
        "id": course.key.id,
        "subject": course["subject"],
        "number": course["number"],
        "title": course["title"],
        "term": course["term"],
        "instructor_id": course["instructor_id"],
        "self": build_course_url(str(course.key.id))
    }), 200

@courses_bp.route("/courses/<int:course_id>", methods=["PATCH"])
@requires_auth
def update_course(course_id):
    requester = get_user_by_sub(request.user["sub"])
    if not requester:
        return error_response("Unauthorized", 401)

    key = datastore_client.key("courses", course_id)
    course = datastore_client.get(key)
    if not course:
        return error_response("You don't have permission on this resource", 403)

    if requester["role"] != "admin":
        return error_response("You don't have permission on this resource", 403)

    data = request.get_json()
    if "instructor_id" in data:
        instructor = get_user_by_id(data["instructor_id"])
        if not instructor or instructor["role"] != "instructor":
            return error_response("The request body is invalid", 400)

    for field in ("subject", "number", "title", "term", "instructor_id"):
        if field in data:
            course[field] = data[field]

    datastore_client.put(course)

    return jsonify({
        "id": course.key.id,
        "subject": course["subject"],
        "number": course["number"],
        "title": course["title"],
        "term": course["term"],
        "instructor_id": course["instructor_id"],
        "self": build_course_url(str(course.key.id))
    }), 200

@courses_bp.route("/courses/<int:course_id>", methods=["DELETE"])
@requires_auth
def delete_course(course_id):
    requester = get_user_by_sub(request.user["sub"])
    if not requester:
        return error_response("Unauthorized", 401)

    key = datastore_client.key("courses", course_id)
    course = datastore_client.get(key)
    if not course or requester["role"] != "admin":
        return error_response("You don't have permission on this resource", 403)

    datastore_client.delete(key)
    return "", 204

@courses_bp.route("/courses/<int:course_id>/students", methods=["PATCH"])
@requires_auth
def update_enrollment(course_id):
    requester = get_user_by_sub(request.user["sub"])
    if not requester:
        return error_response("Unauthorized", 401)

    key = datastore_client.key("courses", course_id)
    course = datastore_client.get(key)
    if not course:
        return error_response("You don't have permission on this resource", 403)

    if requester["role"] != "admin" and requester["sub"] != get_user_by_id(course["instructor_id"])["sub"]:
        return error_response("You don't have permission on this resource", 403)

    data = request.get_json()
    add = data.get("add", [])
    remove = data.get("remove", [])

    if not isinstance(add, list) or not isinstance(remove, list):
        return error_response("Enrollment data is invalid", 409)
    if any(id_ in remove for id_ in add):
        return error_response("Enrollment data is invalid", 409)

    for sid in add + remove:
        user = get_user_by_id(sid)
        if not user or user["role"] != "student":
            return error_response("Enrollment data is invalid", 409)

    students = set(course.get("students", []))
    students.update(add)
    students.difference_update(remove)
    course["students"] = list(students)
    datastore_client.put(course)
    return "", 200

@courses_bp.route("/courses/<int:course_id>/students", methods=["GET"])
@requires_auth
def get_enrollment(course_id):
    requester = get_user_by_sub(request.user["sub"])
    if not requester:
        return error_response("Unauthorized", 401)

    key = datastore_client.key("courses", course_id)
    course = datastore_client.get(key)
    if not course:
        return error_response("You don't have permission on this resource", 403)

    if requester["role"] != "admin" and requester["sub"] != get_user_by_id(course["instructor_id"])["sub"]:
        return error_response("You don't have permission on this resource", 403)

    return jsonify(course.get("students", [])), 200
