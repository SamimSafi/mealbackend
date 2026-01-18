import sys
try:
    import analysis
    print("SUCCESS: analysis module imported")
    print("router found:", hasattr(analysis, 'router'))
except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
