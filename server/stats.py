from functools import wraps
import time

def measure_time(label):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()

            result = func(*args, **kwargs)

            duration = time.perf_counter() - start
            print(f"{label}: {duration:.2f} seconds")
            
            return result
        return wrapper
    return decorator

# usage: @measure_time("Batch stock fetch")