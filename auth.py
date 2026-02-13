import os
from functools import wraps
from flask import request, jsonify
import requests
from jose import jwt, JWTError

AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "dev-placeholder.auth0.com")
API_IDENTIFIER = os.environ.get("API_IDENTIFIER", "https://tarpaulin.api")
ALGORITHMS = ["RS256"]

def error_unauthorized():
    return jsonify({"Error": "Unauthorized"}), 401

def get_token_auth_header():
    auth = request.headers.get("Authorization", None)
    if not auth:
        return None, "Missing Authorization Header"

    parts = auth.split()
    if parts[0].lower() != "bearer":
        return None, "Authorization must start with Bearer"
    elif len(parts) == 1:
        return None, "Token not found"
    elif len(parts) > 2:
        return None, "Authorization header must be Bearer token"

    return parts[1], None

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token, err = get_token_auth_header()
        if err:
            return error_unauthorized()

        try:
            jwks = requests.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json").json()
            unverified_header = jwt.get_unverified_header(token)

            rsa_key = {}
            for key in jwks["keys"]:
                if key["kid"] == unverified_header["kid"]:
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"]
                    }
                    break

            if not rsa_key:
                return error_unauthorized()

            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=ALGORITHMS,
                audience=API_IDENTIFIER,
                issuer=f"https://{AUTH0_DOMAIN}/"
            )

            from datastore import get_user_by_sub
            user = get_user_by_sub(payload["sub"])

            request.user = payload
            return f(*args, **kwargs)

        except JWTError:
            return error_unauthorized()
        except Exception:
            return error_unauthorized()

    return decorated
