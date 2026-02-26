import os
import pytest
from hardware_crawler.database import DatabaseManager

@pytest.fixture
def db_manager(tmp_path):
    # Use a temporary file for the database
    db_path = tmp_path / "test_products.db"
    manager = DatabaseManager(str(db_path))
    yield manager
    # Teardown handled by tmp_path fixture

def test_init_db(db_manager):
    assert os.path.exists(db_manager.db_path)

def test_add_product(db_manager):
    product = {
        "title": "Test Product",
        "price": "100 EUR",
        "link": "http://example.com/product",
        "source": "test_source"
    }
    assert db_manager.add_product(product) is True
    assert db_manager.check_product_exists("http://example.com/product") is True

def test_add_duplicate_product(db_manager):
    product = {
        "title": "Test Product",
        "price": "100 EUR",
        "link": "http://example.com/product",
        "source": "test_source"
    }
    assert db_manager.add_product(product) is True
    # Try adding the same product (same link) again
    assert db_manager.add_product(product) is False

def test_get_all_products(db_manager):
    product1 = {
        "title": "Product 1",
        "price": "50 EUR",
        "link": "http://example.com/1",
        "source": "source1"
    }
    product2 = {
        "title": "Product 2",
        "price": "150 EUR",
        "link": "http://example.com/2",
        "source": "source2"
    }
    db_manager.add_product(product1)
    db_manager.add_product(product2)

    products = db_manager.get_all_products()
    assert len(products) == 2
    # Verify order (descending timestamp)
    assert products[0]["title"] == "Product 2"
    assert products[1]["title"] == "Product 1"
