from flask import Blueprint, jsonify, request

from routes.applications import _serialize as serialize_app
from models import Application
from ml import predictor
from ml.train_model import train as train_model

predictions_bp = Blueprint("predictions", __name__, url_prefix="/api/predictions")


@predictions_bp.route("/forecast", methods=["GET"])
def get_forecast():
    days = int(request.args.get("days", 7))
    days = min(max(days, 1), 14)

    try:
        result = predictor.forecast(days=days, auto_train=True)
    except predictor.ModelNotTrainedError as e:
        return jsonify({"error": str(e)}), 409
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 422

    apps = [serialize_app(a) for a in Application.query.all()]
    risks = predictor.breach_risk(apps, result)
    recs = predictor.recommendations(result, risks, result["today_productivity_score"])

    return jsonify(
        {
            **result,
            "breach_risk": risks,
            "recommendations": recs,
        }
    )


@predictions_bp.route("/train", methods=["POST"])
def train():
    try:
        metadata = train_model()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 422
    return jsonify(metadata)


@predictions_bp.route("/model-info", methods=["GET"])
def model_info():
    meta = predictor.get_metadata()
    if not meta:
        return jsonify({"trained": False})
    return jsonify({"trained": True, **meta})
