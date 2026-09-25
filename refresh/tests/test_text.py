from __future__ import annotations

from refresh.text import content_hash, html_to_text


def test_should_strip_script_and_style_when_cleaning_html():
    html = "<html><head><style>.a{color:red}</style></head><body>" \
           "<script>alert(1)</script><p>Free tier: 100 requests</p></body></html>"
    text = html_to_text(html)
    assert "alert" not in text
    assert "color:red" not in text
    assert "Free tier: 100 requests" in text


def test_should_drop_nav_and_footer_when_cleaning_html():
    html = "<body><nav>Home About</nav><main>Pricing details</main><footer>Copyright 2026</footer></body>"
    text = html_to_text(html)
    assert "Home" not in text
    assert "Copyright" not in text
    assert "Pricing details" in text


def test_should_collapse_whitespace_when_cleaning_html():
    html = "<p>Free   tier\n\n  with   spaces</p>"
    text = html_to_text(html)
    assert "  " not in text
    assert text == "Free tier with spaces"


def test_should_cap_length_when_text_exceeds_max_chars():
    html = "<p>" + ("x" * 30_000) + "</p>"
    text = html_to_text(html)
    assert len(text) == 20_000


def test_should_be_stable_when_hashing_same_text_twice():
    assert content_hash("hello world") == content_hash("hello world")


def test_should_differ_when_hashing_different_text():
    assert content_hash("hello") != content_hash("world")
