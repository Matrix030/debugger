"""Candidate question endpoints: listing, detail, navigation data."""


def test_list_questions(client):
    response = client.get("/api/questions")
    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == ["sample-question", "other-question"]
    assert data[0]["index"] == 0
    assert data[1]["index"] == 1
    assert all(item["total"] == 2 for item in data)
    assert data[0]["difficulty"] == "easy"
    assert data[1]["difficulty"] == "medium"
    assert data[0]["tags"] == ["debugging", "sample"]


def test_question_detail(client):
    response = client.get("/api/questions/sample-question")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Sample Question"
    assert data["function_name"] == "double_it"
    assert data["language"] == "python"
    assert "def double_it" in data["starter_code"]
    assert data["index"] == 0
    assert data["total"] == 2
    assert data["time_limit_seconds"] == 5
    assert data["memory_limit_mb"] == 256
    assert len(data["visible_tests"]) == 2
    assert data["visible_tests"][0] == {
        "name": "doubles two",
        "args": [2],
        "expected": 4,
    }


def test_question_detail_renders_markdown(client):
    data = client.get("/api/questions/sample-question").json()
    assert "<h3>Task</h3>" in data["description_html"]
    assert "<li>Make it work.</li>" in data["description_html"]


def test_unknown_question_404(client):
    assert client.get("/api/questions/nope").status_code == 404
    response = client.post("/api/run", json={"question_id": "nope", "code": "x = 1"})
    assert response.status_code == 404
    response = client.post("/api/submit", json={"question_id": "nope", "code": "x = 1"})
    assert response.status_code == 404


def test_candidate_page_serves(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "DebugLab" in response.text
    assert "code-editor" in response.text
