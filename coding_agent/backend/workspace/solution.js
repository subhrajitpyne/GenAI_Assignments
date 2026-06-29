function calculateFactorial(n) {
    if (n === null) return null;
    if (typeof n !== 'number') return null;
    if (n < 0) return null;
    
    let factorial = 1;
    for (let i = 1; i <= n; i++) {
        factorial *= i;
    }
    return factorial;
}