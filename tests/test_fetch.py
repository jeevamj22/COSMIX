from app.fetch_page import assert_public_url, ingredients_from_html, shop_wall_message
import pytest


def test_local_and_private_links_are_blocked():
    for url in [
        "http://127.0.0.1/admin",
        "http://10.0.0.8/secret",
        "http://192.168.1.20/camera",
        "http://169.254.169.254/latest",
        "file:///C:/Users/secret.txt",
        "javascript:alert(1)",
        "https://user:pass@example.com/item",
    ]:
        with pytest.raises(ValueError):
            assert_public_url(url)


def test_html_ingredient_list_is_read_from_the_heading():
    html = """
    <html><head><title>Shop serum</title></head>
    <body>
      <h1>Shop serum</h1>
      <p>A nice glow story with no chemistry.</p>
      <h2>Ingredients</h2>
      <p>Aqua, Glycerin, Niacinamide, Phenoxyethanol</p>
      <h2>How to use</h2>
      <p>Apply daily.</p>
    </body></html>
    """
    parsed = ingredients_from_html(html)
    assert "Niacinamide" in parsed["ingredients"]
    assert "Apply daily" not in parsed["ingredients"]


def test_json_ld_ingredients_are_read():
    html = """
    <html><head>
      <script type="application/ld+json">
        {"@type":"Product","name":"Night cream","ingredients":"Aqua, Glycerin, Retinol, Dimethicone"}
      </script>
    </head><body><h1>Night cream</h1></body></html>
    """
    parsed = ingredients_from_html(html)
    assert "Retinol" in parsed["ingredients"]
    assert parsed["product_name"] == "Night cream"


def test_amazon_shopping_wall_is_named():
    html = """
    <html><head><title>Amazon.in</title></head>
    <body><h1>Click the button below to continue shopping</h1>
    <a>Continue shopping</a></body></html>
    """
    message = shop_wall_message(html, "https://www.amazon.in/dp/B0G4WQX1WR")
    assert "amazon.in" in message
    assert "shopping wall" in message
    assert "tube" in message


def test_a_real_product_page_is_not_called_a_wall():
    html = "<html><body><p>Continue shopping</p>" + ("Aqua, Glycerin, Niacinamide. " * 400) + "</body></html>"
    assert shop_wall_message(html, "https://www.example.com/wash") == ""
