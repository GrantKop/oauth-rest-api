from google.cloud import datastore
import os

client = datastore.Client()

def get_user_by_sub(sub):
    query = client.query(kind="users")
    query.add_filter("sub", "=", sub)
    results = list(query.fetch(limit=1))
    return results[0] if results else None

def get_user_by_id(user_id):
    key = client.key("users", int(user_id))
    return client.get(key)

def get_all_users():
    query = client.query(kind="users")
    return [dict(user) | {"id": user.key.id} for user in query.fetch()]
