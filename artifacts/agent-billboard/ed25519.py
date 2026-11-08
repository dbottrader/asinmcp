# Pure-Python Ed25519 (RFC 8032), reference implementation after
# Bernstein, Duif, Lange, Schwabe, Yang ("High-speed high-security signatures").
# Standard library only (hashlib) — no PyNaCl / cryptography dependency, so the
# board tools run anywhere Python 3 runs. Cross-checked against Node's native
# ed25519 (see README.md §verification) — do not edit the math.
import hashlib

b = 256
q = 2**255 - 19
l = 2**252 + 27742317777372353535851937790883648493


def H(m):
    return hashlib.sha512(m).digest()


def expmod(b_, e, m):
    if e == 0:
        return 1
    t = expmod(b_, e // 2, m) ** 2 % m
    if e & 1:
        t = (t * b_) % m
    return t


def inv(x):
    return expmod(x, q - 2, q)


d = -121665 * inv(121666) % q
I = expmod(2, (q - 1) // 4, q)


def xrecover(y):
    xx = (y * y - 1) * inv(d * y * y + 1)
    x = expmod(xx, (q + 3) // 8, q)
    if (x * x - xx) % q != 0:
        x = (x * I) % q
    if x % 2 != 0:
        x = q - x
    return x


By = 4 * inv(5) % q
Bx = xrecover(By)
B = [Bx % q, By % q]


def edwards(P, Q):
    # Twisted Edwards addition for a = -1: -x^2 + y^2 = 1 + d x^2 y^2.
    # y3 uses (y1*y2 + x1*x2) because -a = +1; the minus form is for a = +1
    # and produces off-curve points here (caught by l*B == identity failing).
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * inv(1 + d * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * inv(1 - d * x1 * x2 * y1 * y2)
    return [x3 % q, y3 % q]


def scalarmult(P, e):
    if e == 0:
        return [0, 1]
    Q = scalarmult(P, e // 2)
    Q = edwards(Q, Q)
    if e & 1:
        Q = edwards(Q, P)
    return Q


def encodeint(y):
    bits = [(y >> i) & 1 for i in range(b)]
    return bytes([sum([bits[i * 8 + j] << j for j in range(8)])
                  for i in range(b // 8)])


def encodepoint(P):
    x, y = P
    bits = [(y >> i) & 1 for i in range(b - 1)] + [x & 1]
    return bytes([sum([bits[i * 8 + j] << j for j in range(8)])
                  for i in range(b // 8)])


def bit(h, i):
    return (h[i // 8] >> (i % 8)) & 1


def publickey(sk):
    """sk: 32-byte seed. Returns 32-byte public key."""
    h = H(sk)
    a = 2**254 + sum(2**i * bit(h, i) for i in range(3, 254))
    A = scalarmult(B, a)
    return encodepoint(A)


def Hint(m):
    h = H(m)
    return sum(2**i * bit(h, i) for i in range(2 * b))


def signature(m, sk, pk):
    h = H(sk)
    a = 2**254 + sum(2**i * bit(h, i) for i in range(3, 254))
    r = Hint(h[b // 8:b // 4] + m)
    R = scalarmult(B, r)
    S = (r + Hint(encodepoint(R) + pk + m) * a) % l
    return encodepoint(R) + encodeint(S)


def isoncurve(P):
    x, y = P
    return (-x * x + y * y - 1 - d * x * x * y * y) % q == 0


def decodeint(s):
    return sum(2**i * bit(s, i) for i in range(0, b))


def decodepoint(s):
    y = sum(2**i * bit(s, i) for i in range(0, b - 1))
    x = xrecover(y)
    if x & 1 != bit(s, b - 1):
        x = q - x
    P = [x, y]
    if not isoncurve(P):
        raise Exception("not on curve")
    return P


def checkvalid(s, m, pk):
    """Raises unless s is a valid signature of m under pk (both bytes)."""
    if len(s) != b // 4:
        raise Exception("signature length is wrong")
    if len(pk) != b // 8:
        raise Exception("public-key length is wrong")
    R = decodepoint(s[0:b // 8])
    A = decodepoint(pk)
    S = decodeint(s[b // 8:b // 4])
    h = Hint(encodepoint(R) + pk + m)
    if scalarmult(B, S) != edwards(R, scalarmult(A, h)):
        raise Exception("signature does not verify")
