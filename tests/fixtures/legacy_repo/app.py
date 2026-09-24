"""Source-only Flask API fixture for legacy code analysis."""
from flask import Flask, jsonify, request

from repository import find_claim
from services import ClaimsService

app = Flask(__name__)
service = ClaimsService()


@app.route("/claims", methods=["POST"])
def create_claim():
    payload = request.get_json()
    claim_id = service.submit_claim(payload)
    return jsonify({"claimId": claim_id}), 201


@app.route("/claims/<int:claim_id>", methods=["GET"])
def get_claim(claim_id):
    return jsonify(find_claim(claim_id))
