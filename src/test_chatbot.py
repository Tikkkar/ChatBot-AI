from .utils.quick_fixes import detect_product_id_from_context
# test_validation.py
def test_address_validation():
    from utils.quick_fixes import test_address_validation
    test_address_validation()

def test_phone_validation():
    from utils.quick_fixes import test_phone_validation
    test_phone_validation()

def test_product_id_detection():
    context_products = [
        {"id": "prod-1", "name": "Áo vest 1"},
        {"id": "prod-2", "name": "Áo vest 2"}
    ]
    
    # Test case 1: Chỉ định rõ "mẫu 2"
    result = detect_product_id_from_context(
        "Lấy mẫu 2 cho chị",
        context_products
    )
    assert result == "prod-2"
    
    # Test case 2: Chỉ có 1 sản phẩm
    result = detect_product_id_from_context(
        "Gửi về cho chị",
        [context_products[0]]
    )
    assert result == "prod-1"
    
    # Test case 3: Lấy sản phẩm cuối
    result = detect_product_id_from_context(
        "Gửi về cho chị",
        context_products
    )
    assert result == "prod-2"