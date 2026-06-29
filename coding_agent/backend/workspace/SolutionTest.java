import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Assertions.*;

class FactorialTest {

    @Test
    void testFactorialOfZero() {
        assertEquals(1, solution(0));
    }

    @Test
    void testFactorialOfOne() {
        assertEquals(1, solution(1));
    }

    @Test
    void testFactorialOfFive() {
        assertEquals(120, solution(5));
    }

    @Test
    void testFactorialOfNegativeNumber() {
        assertThrows(IllegalArgumentException.class, () -> solution(-1));
    }

    @Test
    void testFactorialOfLargeNumber() {
        assertEquals(3628800, solution(10));
    }
}