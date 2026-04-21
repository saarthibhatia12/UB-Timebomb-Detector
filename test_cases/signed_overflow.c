// Test Case 1: Signed Integer Overflow
// Expected: comparison eliminated at -O2
// UB: x + 1 > x is UB when x = INT_MAX
#include <limits.h>

int always_greater(int x) {
    return x + 1 > x;   // UB: signed overflow
}
