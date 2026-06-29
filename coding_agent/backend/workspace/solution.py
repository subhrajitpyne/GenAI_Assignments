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