"""
Tests for document ingestion: file upload (PDF/text) and text-paste.
"""

MINIMAL_PDF_WITH_TEXT = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 200 100] /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 58 >>
stream
BT /F1 12 Tf 10 50 Td (PATHLIGHT_TEST_MARKER) Tj ET
endstream
endobj
xref
0 6
0000000000 65535 f 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
0
%%EOF"""


def _auth_headers(client, email="doc-user@example.com", password="testpass123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    login_resp = client.post("/api/auth/login", data={"username": email, "password": password})
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_paste_document_creates_record_with_text(client):
    headers = _auth_headers(client)
    resp = client.post(
        "/api/documents/paste",
        json={"doc_type": "job_description", "title": "Acme SWE Intern JD", "text": "We need Python and SQL."},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["extracted_text"] == "We need Python and SQL."
    assert body["doc_type"] == "job_description"
    assert body["storage_filename"].endswith(".txt")


def test_upload_text_file_extracts_text(client):
    headers = _auth_headers(client)
    resp = client.post(
        "/api/documents/upload",
        data={"doc_type": "resume"},
        files={"file": ("resume.txt", b"Skilled in Java and Spring Boot.", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["extracted_text"] == "Skilled in Java and Spring Boot."
    assert body["original_filename"] == "resume.txt"


def test_upload_pdf_extracts_text(client):
    headers = _auth_headers(client)
    resp = client.post(
        "/api/documents/upload",
        data={"doc_type": "resume"},
        files={"file": ("resume.pdf", MINIMAL_PDF_WITH_TEXT, "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "PATHLIGHT_TEST_MARKER" in body["extracted_text"]


def test_upload_rejects_unsupported_content_type(client):
    headers = _auth_headers(client)
    resp = client.post(
        "/api/documents/upload",
        data={"doc_type": "resume"},
        files={"file": ("resume.docx", b"fake docx bytes", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=headers,
    )
    assert resp.status_code == 415


def test_documents_require_auth(client):
    resp = client.get("/api/documents")
    assert resp.status_code == 401


def test_get_document_not_owned_returns_404(client):
    # user A creates a document
    headers_a = _auth_headers(client, email="owner-a@example.com")
    create_resp = client.post(
        "/api/documents/paste",
        json={"doc_type": "other", "title": "Private note", "text": "secret"},
        headers=headers_a,
    )
    doc_id = create_resp.json()["id"]

    # user B tries to fetch it directly by ID
    headers_b = _auth_headers(client, email="owner-b@example.com")
    resp = client.get(f"/api/documents/{doc_id}", headers=headers_b)
    assert resp.status_code == 404
