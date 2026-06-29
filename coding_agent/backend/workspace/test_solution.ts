import { solution } from './solution';

describe('Factorial Function Tests', () => {
    test('should return 1 for factorial of 0', () => {
        expect(solution(0)).toBe(1);
    });

    test('should return 1 for factorial of 1', () => {
        expect(solution(1)).toBe(1);
    });

    test('should return 120 for factorial of 5', () => {
        expect(solution(5)).toBe(120);
    });

    test('should return 720 for factorial of 6', () => {
        expect(solution(6)).toBe(720);
    });

    test('should return 40320 for factorial of 8', () => {
        expect(solution(8)).toBe(40320);
    });

    test('should throw an error for negative input', () => {
        expect(() => solution(-1)).toThrow('Input must be a non-negative integer');
    });

    test('should return 1 for factorial of 2 (boundary case)', () => {
        expect(solution(2)).toBe(2);
    });

    test('should return 3628800 for factorial of 10 (large input)', () => {
        expect(solution(10)).toBe(3628800);
    });
});