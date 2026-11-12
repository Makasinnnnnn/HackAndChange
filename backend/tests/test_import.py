import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("catalog_importer", ROOT / "scripts/import_catalog.py")
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


def test_normalization_removes_active_html_and_preserves_text():
    assert (
        importer.plain("<p>План &amp; действие</p><script>steal()</script><style>body{}</style>")
        == "План & действие"
    )


def test_unknown_routes_are_not_fabricated(monkeypatch, tmp_path):
    monkeypatch.setattr(importer, "ROOT", tmp_path)
    assert importer.source_url("document-slug", "document") is None
    assert importer.source_url("javascript:alert(1)", "article") is None
    assert importer.source_url("//evil.test/path", "article") is None
    assert (
        importer.source_url("existing-slug", "article") == "https://kurs.alfabank.ru/articles/existing-slug/"
    )


def test_paid_descriptions_are_bounded():
    assert len(importer.plain("<p>" + ("Содержание " * 200) + "</p>", 180)) == 180


def test_course_null_price_is_free_but_subscription_is_preserved():
    assert importer.price_and_access("course", {"Cost": None}, set()) == (0, "free")
    assert importer.price_and_access("course", {"Cost": None}, {"По подписке"}) == (0, "subscription")
    assert importer.price_and_access("course", {"Cost": None}, set(), True) == (0, "subscription")
    assert importer.price_and_access("course", {"Cost": 3990}, {"Платный"}) == (3990, "paid")
    assert importer.price_and_access("podcast", {"Cost": None}, set()) == (None, "unknown")
    assert importer.price_and_access("article", {"IsPublic": False}, {"Открытый"}) == (None, "unknown")
