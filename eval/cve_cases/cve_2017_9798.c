// CVE-2017-9798 — Apache Optionsbleed (simplified pattern)
// Pattern: Uninitialized stack variable is read when a code path
// fails to assign it. At -O2, the compiler may propagate undef
// or return garbage data.
//
// NOTE: Simplified reproduction of the uninitialized read pattern.

int get_options(int flag) {
    int result;              // uninitialized
    if (flag > 10) {
        result = flag * 2;
    }
    // Missing else: result is indeterminate when flag <= 10
    return result;           // UB: may return garbage
}
