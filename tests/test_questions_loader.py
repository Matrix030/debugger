"""Question file loading and validation."""

from pathlib import Path

import pytest

from app.questions import (
    QuestionBank,
    QuestionValidationError,
    load_question_file,
    question_bank,
)
from tests.conftest import question_dict, write_question


def test_seed_questions_load_and_validate():
    """The shipped question bank loads: at least 5 valid questions."""
    questions = question_bank.all()
    assert len(questions) >= 5
    for question in questions:
        assert question.id
        assert len(question.visible_tests) >= 2
        assert len(question.hidden_tests) >= 3
        assert question.interviewer_notes.strip()
        assert question.solution.strip()


def test_example_template_is_skipped():
    ids = [question.id for question in question_bank.all()]
    seen_files = [path.name for path in Path("data/questions").glob("*.yaml")]
    assert "example.yaml" in seen_files
    assert "example-question" not in ids


def test_questions_ordered_by_filename(questions_dir):
    bank = QuestionBank(questions_dir)
    assert [q.id for q in bank.all()] == ["sample-question", "other-question"]
    assert bank.index_of("other-question") == 1
    assert bank.index_of("missing") == -1


def test_example_yaml_excluded_from_bank(questions_dir):
    write_question(questions_dir, "example.yaml", question_dict(id="template-q"))
    bank = QuestionBank(questions_dir)
    assert "template-q" not in [q.id for q in bank.all()]


def test_mtime_cache_reloads_on_change(questions_dir):
    import os

    bank = QuestionBank(questions_dir)
    assert len(bank.all()) == 2
    path = write_question(questions_dir, "003_new.yaml", question_dict(id="brand-new"))
    os.utime(path, (path.stat().st_atime + 5, path.stat().st_mtime + 5))
    assert "brand-new" in [q.id for q in bank.all()]


def test_missing_required_field_rejected(tmp_path):
    data = question_dict()
    del data["solution"]
    path = write_question(tmp_path, "bad.yaml", data)
    with pytest.raises(QuestionValidationError):
        load_question_file(path)


def test_bad_difficulty_rejected(tmp_path):
    path = write_question(tmp_path, "bad.yaml", question_dict(difficulty="impossible"))
    with pytest.raises(QuestionValidationError):
        load_question_file(path)


def test_bad_id_slug_rejected(tmp_path):
    path = write_question(tmp_path, "bad.yaml", question_dict(id="Not A Slug!"))
    with pytest.raises(QuestionValidationError):
        load_question_file(path)


def test_function_missing_from_starter_rejected(tmp_path):
    path = write_question(
        tmp_path,
        "bad.yaml",
        question_dict(starter_code="def wrong_name(n):\n    return n\n"),
    )
    with pytest.raises(QuestionValidationError, match="starter_code"):
        load_question_file(path)


def test_function_missing_from_solution_rejected(tmp_path):
    path = write_question(
        tmp_path,
        "bad.yaml",
        question_dict(solution="def wrong_name(n):\n    return n * 2\n"),
    )
    with pytest.raises(QuestionValidationError, match="solution"):
        load_question_file(path)


def test_invalid_python_rejected(tmp_path):
    path = write_question(
        tmp_path,
        "bad.yaml",
        question_dict(starter_code="def double_it(n:\n    return n\n"),
    )
    with pytest.raises(QuestionValidationError):
        load_question_file(path)


def test_empty_tests_rejected(tmp_path):
    path = write_question(tmp_path, "bad.yaml", question_dict(hidden_tests=[]))
    with pytest.raises(QuestionValidationError):
        load_question_file(path)


def test_duplicate_ids_rejected(questions_dir):
    write_question(questions_dir, "003_dupe.yaml", question_dict())
    bank = QuestionBank(questions_dir)
    with pytest.raises(QuestionValidationError, match="duplicate"):
        bank.all()


def test_unknown_extra_field_rejected(tmp_path):
    path = write_question(tmp_path, "bad.yaml", question_dict(surprise_field="oops"))
    with pytest.raises(QuestionValidationError):
        load_question_file(path)
