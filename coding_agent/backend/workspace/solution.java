public class FactorialCalculator {
    public static long calculateFactorial(Integer number) {
        if (number == null) {
            throw new IllegalArgumentException("Input cannot be null");
        }
        if (!(number instanceof Integer)) {
            throw new IllegalArgumentException("Input must be an integer");
        }
        if (number < 0) {
            throw new IllegalArgumentException("Input must be a non-negative integer");
        }
        
        long factorial = 1;
        for (int i = 1; i <= number; i++) {
            factorial *= i;
        }
        return factorial;
    }
}