// CVE-2014-3153 — Linux kernel futex integer overflow
// Pattern: Signed integer overflow in a bounds check allows
// out-of-range access. The optimizer may remove the check
// entirely since signed overflow is UB.
//
// NOTE: Simplified reproduction of the overflow-in-bounds-check pattern.

int check_bounds(int offset, int size) {
    // Vulnerable: offset + size can overflow a signed int
    if (offset + size > 4096)
        return -1;   // bounds check — may be removed at -O2
    return offset + size;
}
