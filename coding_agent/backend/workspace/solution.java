public class FactorialCalculator {
    public static long calculateFactorial(int number) {
        if (number == 0 || number == 1) {
            return 1;
        }
        if (number < 0) {
            throw new IllegalArgumentException("Number must be non-negative");
        }
        long factorial = 1;
        for (int i = 2; i <= number; i++) {
            factorial *= i;
        }
        return factorial;
    }
}