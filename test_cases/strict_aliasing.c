// Test Case 3: Strict Aliasing Violation
// Expected: load may be reordered or dropped at -O2
// UB: accessing int memory through float pointer

int alias_bug(int *ip) {
    float *fp = (float *)ip;   // UB: strict aliasing
    *fp = 1.0f;
    return *ip;                 // may see stale value at -O2
}
