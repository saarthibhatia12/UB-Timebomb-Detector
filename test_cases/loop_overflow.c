// Test Case 5: Signed Overflow in Loop Bound
// Expected: loop exit condition removed at -O2
// UB: signed int i will overflow past INT_MAX
// WARNING: Do NOT execute this at -O2 — it becomes an infinite loop.

int count_up(int limit) {
    int count = 0;
    for (int i = 0; i < limit; i++) {
        if (i + 1 < 0) return -1;   // overflow guard removed at O2
        count++;
    }
    return count;
}
