function calculateFactorial(num: number): number | null {
    if (num === null) return null;
    if (typeof num !== 'number') throw new Error('Invalid type');
    if (num < 0) throw new Error('Negative input is not allowed');

    let factorial = 1;
    for (let i = 1; i <= num; i++) {
        factorial *= i;
    }
    return factorial;
}