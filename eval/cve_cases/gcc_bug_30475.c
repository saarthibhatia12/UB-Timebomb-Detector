// GCC Bug #30475 — Signed overflow in loop bound
// Pattern: Loop counter wraps around via signed overflow.
// The optimizer assumes signed overflow never happens,
// so it removes the overflow guard, creating a potential infinite loop.
//
// NOTE: This is a simplified reproduction of the pattern.

int loop_wraps(int n) {
    int i, count = 0;
    for (i = 0; i < n; i++) {
        if (i + 1 < 0)   // overflow guard — removed at -O2
            return -1;
        count++;
    }
    return count;
}
