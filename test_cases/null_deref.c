// Test Case 2: Null Pointer Dereference
// Expected: null check removed at -O2
// UB: dereferencing ptr before null check

int get_value(int *ptr) {
    int val = *ptr;       // UB if ptr is NULL
    if (ptr == 0)         // dead code at -O2
        return -1;
    return val;
}
