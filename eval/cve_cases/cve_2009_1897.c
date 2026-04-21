// CVE-2009-1897 — Linux kernel null pointer dereference
// Pattern: Pointer is dereferenced before null check.
// At -O2, the compiler concludes the pointer cannot be null
// (since dereferencing null is UB), and removes the check.
//
// NOTE: Simplified reproduction of the kernel sock_sendmsg pattern.

struct sock {
    int sk_family;
    int sk_flags;
};

int sock_sendmsg(struct sock *sk) {
    int family = sk->sk_family;   // UB if sk == NULL
    if (sk == 0)                   // dead code at -O2
        return -1;
    return family;
}
