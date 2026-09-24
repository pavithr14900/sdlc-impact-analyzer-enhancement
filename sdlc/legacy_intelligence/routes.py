"""Flask routes for the Legacy Code Intelligence capability."""
from flask import Blueprint, jsonify, request

from . import repository, service
from sdlc.llm import AIProviderError
from pathlib import Path
import io
import tempfile
import zipfile
from flask import send_file

legacy_intelligence_bp = Blueprint("legacy_intelligence", __name__, url_prefix="/api/legacy-intelligence")


def failure(message, status):
    return jsonify(success=False, error=str(message)), status


@legacy_intelligence_bp.post("/analyze")
def analyze():
    try:
        analysis = service.start_analysis(request.get_json(silent=True))
        return jsonify(success=True, analysis=analysis), 202
    except ValueError as exc:
        return failure(exc, 400)


@legacy_intelligence_bp.get("/recent")
def recent():
    return jsonify(success=True, analyses=repository.recent())


@legacy_intelligence_bp.get("/<analysis_id>")
def analysis(analysis_id):
    value = repository.get(analysis_id)
    return jsonify(success=True, analysis=value) if value else failure("Analysis not found.", 404)


@legacy_intelligence_bp.delete("/<analysis_id>")
def delete_analysis(analysis_id):
    if not repository.delete(analysis_id):
        return failure("Analysis not found.", 404)
    return jsonify(success=True, analysisId=analysis_id)


@legacy_intelligence_bp.get("/<analysis_id>/<section>")
def analysis_section(analysis_id, section):
    key = {"overview": "overview", "architecture": "architecture", "business-rules": "businessRules", "flows": "flows"}.get(section)
    if not key:
        return failure("Unknown analysis section.", 404)
    value = repository.get(analysis_id)
    if value is None:
        return failure("Analysis not found.", 404)
    return jsonify({"success": True, key: value[key]})


@legacy_intelligence_bp.post("/chat")
def chat():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("analysisId"), str) or not isinstance(payload.get("question"), str) or not 1 <= len(payload["question"].strip()) <= 4000:
        return failure("Provide an analysisId and a question between 1 and 4000 characters.", 400)
    try:
        value = service.require_completed(payload["analysisId"])
        from .agents import answer_question
        result = answer_question(value, payload["question"].strip())
        # `answer_question` may return either a dict (modern) or a tuple (answer, evidence)
        if isinstance(result, dict):
            return jsonify(success=True, **result)
        if isinstance(result, (list, tuple)) and len(result) >= 2:
            answer, evidence = result[0], result[1]
            return jsonify(success=True, answer=answer, evidence=evidence)
        # Fallback: return the raw result as a string
        return jsonify(success=True, answer=str(result))
    except LookupError as exc:
        return failure(exc, 404)
    except RuntimeError as exc:
        return failure(exc, 409)
    except AIProviderError as exc:
        return failure(str(exc), 502)
    except Exception:
        return failure("The selected AI engine could not answer this question. Check the backend AI configuration and retry.", 502)


@legacy_intelligence_bp.post("/<analysis_id>/documentation")
def documentation(analysis_id):
    from .documentation import DOC_TYPES, generate_documentation
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("types"), list) or not payload["types"] or any(not isinstance(kind, str) or kind not in DOC_TYPES for kind in payload["types"]):
        return failure("Select one or more supported documentation types.", 400)
    try:
        value = service.require_completed(analysis_id)
        from .document_pack import author_documentation
        return jsonify(success=True, documents=author_documentation(value, list(dict.fromkeys(payload["types"]))))
    except LookupError as exc:
        return failure(exc, 404)
    except RuntimeError as exc:
        return failure(exc, 409)
    except Exception:
        return failure("Documentation could not be generated. Check the backend logs and retry.", 500)



@legacy_intelligence_bp.get("/<analysis_id>/documentation/pdf")
def documentation_pdf(analysis_id):
    """Generate (if needed) and return PDF(s) for the requested analysis.

    Query params:
      - type: one of the DOC_TYPES or 'all' (default 'all')

    If a single PDF is requested, returns it as an attachment. If multiple
    PDFs are present (e.g. 'all'), returns a ZIP archive containing them.
    """
    from .documentation import DOC_TYPES, generate_documentation

    doc_type = request.args.get("type", "all")
    if doc_type != "all" and doc_type not in DOC_TYPES:
        return failure("Unknown document type.", 400)

    try:
        value = service.require_completed(analysis_id)
    except LookupError as exc:
        return failure(exc, 404)
    except RuntimeError as exc:
        return failure(exc, 409)

    from .document_pack import load_documents, render_saved_pdf
    try:
        requested = request.args.get("types", "")
        selected = list(dict.fromkeys(requested.split(","))) if requested else None
        documents = load_documents(analysis_id, selected if doc_type == "all" else [doc_type])
        pdf_files = [(render_saved_pdf(analysis_id, doc), f"{analysis_id}-{doc['type']}.pdf") for doc in documents]
    except ValueError as exc:
        return failure(exc, 400)
    except Exception:
        return failure("Unable to export the saved documents. Retry the download.", 500)

    if not pdf_files:
        return failure("No PDFs available for the selected analysis and type.", 404)

    if len(pdf_files) == 1:
        path, download_name = pdf_files[0]
        return send_file(str(path), as_attachment=True, download_name=download_name)

    # Multiple PDFs -> return a ZIP
    tmp = tempfile.SpooledTemporaryFile()
    with zipfile.ZipFile(tmp, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, arcname in pdf_files:
            zf.write(str(path), arcname)
    tmp.seek(0)
    return send_file(tmp, as_attachment=True, download_name=f"{analysis_id}-documentation.zip", mimetype="application/zip")


@legacy_intelligence_bp.get("/<analysis_id>/documentation")
def saved_documentation(analysis_id):
    from .document_pack import load_documents
    try:
        service.require_completed(analysis_id)
        return jsonify(success=True, documents=load_documents(analysis_id))
    except LookupError as exc:
        return failure(exc, 404)
    except (RuntimeError, ValueError) as exc:
        return failure(exc, 409)


@legacy_intelligence_bp.get("/confluence/status")
def confluence_status():
    from .confluence import connection_status
    return jsonify(success=True, **connection_status())


@legacy_intelligence_bp.post("/<analysis_id>/confluence/publish")
def publish_confluence(analysis_id):
    from .confluence import publish_documents
    from .documentation import DOC_TYPES
    payload = request.get_json(silent=True)
    documents = payload.get("documents") if isinstance(payload, dict) else None
    if not isinstance(documents, list) or not 1 <= len(documents) <= len(DOC_TYPES) or any(
        not isinstance(item, dict) or item.get("type") not in DOC_TYPES or not isinstance(item.get("revision"), str)
        for item in documents
    ) or len({item["type"] for item in documents}) != len(documents):
        return failure("Select generated documents with their reviewed revisions.", 400)
    try:
        value = service.require_completed(analysis_id)
        return jsonify(success=True, **publish_documents(value, documents))
    except LookupError as exc:
        return failure(exc, 404)
    except ValueError as exc:
        return failure(exc, 400)
    except RuntimeError as exc:
        return failure(exc, 502)
    except Exception:
        return failure("Publishing could not be completed. Check the connection and retry.", 502)
