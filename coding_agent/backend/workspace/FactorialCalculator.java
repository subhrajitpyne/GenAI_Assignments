public class FactorialCalculator {
    public static long factorial(Integer n) {
        if (n == null) { // Check for None FIRST
            throw new IllegalArgumentException("Invalid input");
        }
        if (!(n instanceof Integer)) { // Check for wrong type
            throw new IllegalArgumentException("Invalid input");
        }
        if (n < 0) { // Check for invalid values
            throw new IllegalArgumentException("Invalid input");
        }
        long result = 1;
        for (int i = 1; i <= n; i++) {
            result *= i;
        }
        return result;
    }
}