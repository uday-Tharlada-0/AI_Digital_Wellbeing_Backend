from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


TOKEN_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def create_mobile_token(user_id):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])

    return serializer.dumps({
        "user_id": user_id
    })


def verify_mobile_token(token):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])

    try:
        data = serializer.loads(
            token,
            max_age=TOKEN_MAX_AGE
        )

        return data.get("user_id")

    except (BadSignature, SignatureExpired):
        return None