def factorial(n):
    if n is None:
        return "Error: Input must be a non-negative integer"
    if not isinstance(n, int):
        return "Error: Input must be a non-negative integer"
    if n < 0:
        return "Error: Input must be a non-negative integer"
    
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

calculate_factorial = factorial

def test_calculate_factorial_happy_path():
    assert calculate_factorial(5) == 120
    assert calculate_factorial(3) == 6
    assert calculate_factorial(1) == 1
    assert calculate_factorial(4) == 24

def test_calculate_factorial_edge_cases():
    assert calculate_factorial(0) == 1
    assert calculate_factorial(None) == "Error: Input must be a non-negative integer"
    assert calculate_factorial(-1) == "Error: Input must be a non-negative integer"

def test_calculate_factorial_boundary_values():
    assert calculate_factorial(2) == 2
    assert calculate_factorial(10) == 3628800

def test_calculate_factorial_large_number():
    assert calculate_factorial(20) == 2432902008176640000

def test_calculate_factorial_non_integer_input():
    assert calculate_factorial(5.5) == "Error: Input must be a non-negative integer"
    assert calculate_factorial("five") == "Error: Input must be a non-negative integer"
