describe('solution', () => {
  it('should return correct factorial for positive integers', () => {
    expect(solution(5)).toBe(120);
  });
  it('should return 1 for the factorial of zero', () => {
    expect(solution(0)).toBe(1);
  });
  it('should return null for negative integers', () => {
    expect(solution(-5)).toBeNull();
  });
  it('should return correct factorial for large numbers', () => {
    expect(solution(10)).toBe(3628800);
  });
  it('should handle non-integer inputs gracefully', () => {
    expect(solution(3.5)).toBeNull();
  });
});