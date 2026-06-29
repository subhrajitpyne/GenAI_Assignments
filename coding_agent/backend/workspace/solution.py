def calculate_factorial(n):
    if n is None:
        return "Error: Input must be a non-negative integer"
    if not isinstance(n, int):
        return "Error: Input must be a non-negative integer"
    if n < 0:
        return "Error: Input must be a non-negative integer"
    factorial = 1
    for i in range(1, n + 1):
        factorial *= i
    return factorial