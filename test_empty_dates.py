from analysis import parse_date_param
from fastapi import HTTPException

try:
    result = parse_date_param("")
    assert result is None, f"Expected None, got {result}"
    print("[PASS] Empty string returns None")
    
    result = parse_date_param(None)
    assert result is None, f"Expected None, got {result}"
    print("[PASS] None returns None")
    
    result = parse_date_param("2026-01-18")
    assert str(result) == "2026-01-18", f"Expected 2026-01-18, got {result}"
    print("[PASS] Valid date string parsed correctly")
    
    result = parse_date_param("   ")
    assert result is None, f"Expected None for whitespace, got {result}"
    print("[PASS] Whitespace returns None")
    
    try:
        result = parse_date_param("invalid-date")
        print("[FAIL] Should have raised HTTPException for invalid date")
    except HTTPException as e:
        assert e.status_code == 400
        print("[PASS] Invalid date raises HTTPException with 400 status")
    
    print("\n[SUCCESS] All date parsing tests passed!")
except Exception as e:
    print(f"[FAIL] Test failed: {e}")
    import traceback
    traceback.print_exc()
