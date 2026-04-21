import { ExternalLink } from 'lucide-react';

const CVE_CASES = [
  {
    id: 'GCC #30475',
    title: 'Signed Overflow Loop',
    category: 'signed_overflow',
    description: 'Loop with signed overflow wraparound — optimizer assumes no overflow.',
    year: 2007,
    code: `// GCC Bug #30475 — Signed overflow in loop
// The optimizer removes the overflow check, creating an infinite loop.

int loop_wraps(int n) {
    int i, count = 0;
    for (i = 0; i < n; i++) {
        if (i + 1 < 0)   // overflow guard
            return -1;
        count++;
    }
    return count;
}`,
  },
  {
    id: 'CVE-2009-1897',
    title: 'Null Deref Check Removal',
    category: 'null_deref',
    description: 'Linux kernel: null pointer deref before check — check removed by optimizer.',
    year: 2009,
    code: `// CVE-2009-1897 — Linux kernel null pointer dereference
// Pattern: pointer is dereferenced before the null check.
// Optimizer removes the null check as "impossible."

struct sock {
    int sk_family;
    int sk_flags;
};

int sock_sendmsg(struct sock *sk) {
    int family = sk->sk_family;   // UB if sk is NULL
    if (sk == 0)                   // dead code at -O2
        return -1;
    return family;
}`,
  },
  {
    id: 'CVE-2017-9798',
    title: 'Optionsbleed (Uninit Read)',
    category: 'uninitialized_use',
    description: 'Apache httpd: uninitialized memory read leaked to client.',
    year: 2017,
    code: `// CVE-2017-9798 — Apache Optionsbleed (simplified pattern)
// Uninitialized stack variable read.

int get_options(int flag) {
    int result;              // uninitialized
    if (flag > 10) {
        result = flag * 2;
    }
    // Missing else: result is indeterminate when flag <= 10
    return result;           // UB: may return garbage
}`,
  },
  {
    id: 'CVE-2014-3153',
    title: 'Futex Integer Overflow',
    category: 'signed_overflow',
    description: 'Linux kernel futex: integer overflow in privilege escalation path.',
    year: 2014,
    code: `// CVE-2014-3153 — Simplified integer overflow pattern
// Overflow in bounds check allows out-of-range access.

int check_bounds(int offset, int size) {
    // Vulnerable: offset + size can overflow
    if (offset + size > 4096)
        return -1;   // bounds check — removed at -O2 if overflow assumed impossible
    return offset + size;
}`,
  },
  {
    id: 'CVE-2018-6789',
    title: 'Exim Base64 Overflow',
    category: 'signed_overflow',
    description: 'Exim MTA: one-byte overflow via integer arithmetic bug.',
    year: 2018,
    code: `// CVE-2018-6789 — Simplified integer overflow pattern
// Integer truncation in size calculation.

int decode_size(int encoded_len) {
    // Off-by-one: (3*n/4) truncation can undercount
    int decoded = encoded_len * 3 / 4;    // potential overflow
    if (decoded + 1 < decoded)             // overflow guard removed at -O2
        return -1;
    return decoded;
}`,
  },
];

const CATEGORY_COLORS = {
  signed_overflow: { bg: 'from-accent-red/10 to-transparent', border: 'border-accent-red/20', badge: 'bg-accent-red/15 text-accent-red' },
  null_deref: { bg: 'from-accent-orange/10 to-transparent', border: 'border-accent-orange/20', badge: 'bg-accent-orange/15 text-accent-orange' },
  uninitialized_use: { bg: 'from-accent-yellow/10 to-transparent', border: 'border-accent-yellow/20', badge: 'bg-accent-yellow/15 text-accent-yellow' },
  strict_aliasing: { bg: 'from-accent-purple/10 to-transparent', border: 'border-accent-purple/20', badge: 'bg-accent-purple/15 text-accent-purple' },
};

export default function CVEDatabase({ onLoadCase }) {
  return (
    <div className="px-6 py-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">
            CVE Reproducers
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Simplified analogies of real-world UB vulnerabilities — click to load and analyze
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3 stagger-children">
        {CVE_CASES.map((cve) => {
          const colors = CATEGORY_COLORS[cve.category] || CATEGORY_COLORS.signed_overflow;

          return (
            <button
              key={cve.id}
              onClick={() => onLoadCase(cve.code)}
              className={`group text-left glass-card p-4 bg-gradient-to-b ${colors.bg} border ${colors.border} hover:scale-[1.02] active:scale-[0.99] transition-all duration-200 cursor-pointer`}
            >
              <div className="flex items-start justify-between mb-2">
                <span className={`inline-flex px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${colors.badge}`}>
                  {cve.category.replace('_', ' ')}
                </span>
                <span className="text-[10px] text-gray-500 font-mono">{cve.year}</span>
              </div>

              <h3 className="font-semibold text-sm text-gray-200 mb-1 group-hover:text-white transition-colors">
                {cve.id}
              </h3>
              <p className="text-[11px] text-gray-400 line-clamp-2 leading-relaxed">
                {cve.description}
              </p>

              <div className="mt-3 flex items-center gap-1 text-[10px] text-gray-500 group-hover:text-accent-blue transition-colors">
                <ExternalLink className="w-3 h-3" />
                Load & Analyze
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
