// CVE-2018-6789 — Exim MTA base64 decode overflow
// Pattern: Integer arithmetic produces incorrect size calculation
// due to signed overflow. Overflow guard is removed at -O2.
//
// NOTE: Simplified reproduction of the off-by-one overflow pattern.

int decode_size(int encoded_len) {
    // Off-by-one: (3*n/4) truncation can undercount
    int decoded = encoded_len * 3 / 4;    // potential overflow for large values
    if (decoded + 1 < decoded)             // overflow guard — removed at -O2
        return -1;
    return decoded;
}
