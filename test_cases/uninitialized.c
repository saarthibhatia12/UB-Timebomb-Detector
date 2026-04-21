// Test Case 4: Uninitialized Variable Use
// Expected: undef propagates at -O2
// UB: reading x before assignment

int f(void) {
    int x;
    return x + 1;   // UB: x is indeterminate
}
