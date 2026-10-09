from types import SimpleNamespace

from app.chess_service import delta, evaluation


def result(score, mate=None):
    white_score = SimpleNamespace(score=lambda mate_score=None: score, mate=lambda: mate)
    return SimpleNamespace(score=SimpleNamespace(white=lambda: white_score))


def test_black_perspective_inverts_white_score():
    assert evaluation(result(20), "white").value == 20
    assert evaluation(result(20), "black").value == -20


def test_delta_is_after_minus_before():
    before = evaluation(result(20), "white")
    after = evaluation(result(55), "white")
    assert delta(before, after).value == 35
    assert delta(before, after).display == "+0.35"


def test_mate_is_kept_separate_from_pawns():
    item = evaluation(result(0, mate=3), "white")
    assert item.kind == "mate"
    assert item.display == "+M3"


def test_mate_transition_is_signed():
    before = evaluation(result(20), "white")
    after = evaluation(result(0, mate=1), "white")
    assert delta(before, after).display == "+Mate"
