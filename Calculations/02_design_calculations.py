"""
Two-stage planetary gearbox — design calculations (steps 2-4 of COMPLETION_PLAN.md).

Reproducible: `python 02_design_calculations.py` prints every result and writes
02_design_results.json next to this file.

Methods (simplified, stated explicitly so they can be checked by hand):
  - Gear load capacity: ISO 6336-1/2/3/5:2006 structure. Geometry factors YF, YS by
    method B for external teeth; the ring gear uses the rack (z -> inf) as a conservative
    bound. KHbeta = 1.15 is assumed in section 5 and the base rating; section 12 rechecks
    it with ISO 6336-1 method C from the helix-slope and pin-tilt misalignment budget.
  - Load sharing between planets K_gamma from AGMA 6123 (ISO gives no table value).
  - Bearing life: ISO 281 basic rating life L10.
Strength checks use eta = 1 (all motor torque reaches each gear): an upper bound.
"""
import json
import math
import os

pi = math.pi
rad = math.radians
inv = lambda a: math.tan(a) - a  # involute function

# ---------------------------------------------------------------------------
# 1. Requirements (step 2) — torque basis frozen from the selected motor
# ---------------------------------------------------------------------------
MOTOR = dict(name="Yaskawa SGM7J-08A", P_W=750, n_rated=3000, n_max=6000,
             T_rated=2.39, T_peak=8.36)
I_STAGE = 1 + 72 / 18           # fixed ring, sun in, carrier out
I_TOTAL = I_STAGE ** 2
L_H = 10_000                    # design life [h] at rated torque and rated speed
K_A = 1.25                      # application factor: uniform driver, moderate shocks
SF_MIN, SH_MIN = 1.5, 1.2       # fatigue: bending (R-016), contact (pitting)
SF_STAT_MIN, SH_STAT_MIN = 1.5, 1.0
S0_MIN = 2.0                    # bearing static safety (shock loads)
N_PL = 3
K_GAMMA = 1.16                  # AGMA 6123, 3 planets, no floating member

T2N = MOTOR["T_rated"] * I_TOTAL          # nominal output torque, eta = 1
T2B = MOTOR["T_peak"] * I_TOTAL           # max acceleration torque, eta = 1

# ---------------------------------------------------------------------------
# 2. Gear data
# ---------------------------------------------------------------------------
m, alpha, b = 1.5, rad(20), 15.0
zs, zp, zr = 18, 27, 72
x = 0.0
haP, hfP, rhofP = 1.0 * m, 1.25 * m, 0.38 * m   # ISO 53 basic rack profile A

d = lambda z: m * z
db = lambda z: m * z * math.cos(alpha)
a_w = (d(zs) + d(zp)) / 2
z_min_undercut = 2 / math.sin(alpha) ** 2

def eps_alpha_ext(z1, z2):
    ra1, ra2 = d(z1) / 2 + m, d(z2) / 2 + m
    rb1, rb2 = db(z1) / 2, db(z2) / 2
    g = math.sqrt(ra1**2 - rb1**2) + math.sqrt(ra2**2 - rb2**2) - a_w * math.sin(alpha)
    return g / (pi * m * math.cos(alpha))

def eps_alpha_int(z_pl, z_ring):
    ra2, ra3 = d(z_pl) / 2 + m, d(z_ring) / 2 - m      # ring tip is inside
    rb2, rb3 = db(z_pl) / 2, db(z_ring) / 2
    g = math.sqrt(ra2**2 - rb2**2) - math.sqrt(ra3**2 - rb3**2) + a_w * math.sin(alpha)
    return g / (pi * m * math.cos(alpha))

eps_sp = eps_alpha_ext(zs, zp)
eps_pr = eps_alpha_int(zp, zr)

# ---------------------------------------------------------------------------
# 3. ISO 6336-3 method B form factors (external teeth)
# ---------------------------------------------------------------------------
def form_factors(z, eps_a, z_mate_outer_point=True):
    """YF, YS for an external spur gear cut with the ISO 53 rack (x = 0)."""
    mn = m
    E = pi / 4 * mn - hfP * math.tan(alpha) - (1 - math.sin(alpha)) * rhofP / math.cos(alpha)
    G = rhofP / mn - hfP / mn + x
    H = 2 / z * (pi / 2 - E / mn) - pi / 3
    th = pi / 6
    for _ in range(100):
        th = 2 * G / z * math.tan(th) - H
    sFn = mn * (z * math.sin(pi / 3 - th) + math.sqrt(3) * (G / math.cos(th) - rhofP / mn))
    rhoF = mn * (rhofP / mn + 2 * G**2 / (math.cos(th) * (z * math.cos(th)**2 - 2 * G)))
    dn, dbn, dan = d(z), db(z), d(z) + 2 * m
    den = 2 * math.sqrt((math.sqrt((dan / 2)**2 - (dbn / 2)**2)
                         - pi * dn * math.cos(alpha) * (eps_a - 1) / z)**2 + (dbn / 2)**2)
    a_en = math.acos(dbn / den)
    g_e = (0.5 * pi + 2 * math.tan(alpha) * x) / z + inv(alpha) - inv(a_en)
    a_Fen = a_en - g_e
    hFe = 0.5 * mn * ((math.cos(g_e) - math.sin(g_e) * math.tan(a_Fen)) * den / mn
                      - z * math.cos(pi / 3 - th) - G / math.cos(th) + rhofP / mn)
    YF = 6 * (hFe / mn) * math.cos(a_Fen) / ((sFn / mn)**2 * math.cos(alpha))
    L = sFn / hFe
    qs = sFn / (2 * rhoF)
    YS = (1.2 + 0.13 * L) * qs ** (1 / (1.21 + 2.3 / L))
    return dict(YF=YF, YS=YS, sFn=sFn, rhoF=rhoF, hFe=hFe)

# ---------------------------------------------------------------------------
# 4. Materials (ISO 6336-5, quality MQ)
# ---------------------------------------------------------------------------
MAT = {
    "18CrNiMo7-6 case-hardened (58-62 HRC)": dict(sHlim=1500, sFlim=500, kind="case"),
    "42CrMo4 quenched and tempered (~300 HB)": dict(sHlim=1.313 * 300 + 373, sFlim=0.425 * 300 + 187, kind="qt"),
}
SUN_PLANET_MAT = "18CrNiMo7-6 case-hardened (58-62 HRC)"
RING_MAT = "42CrMo4 quenched and tempered (~300 HB)"

def Z_NT(NL, kind, static=False):
    if static or NL <= 1e5:
        return 1.6 if kind == "case" else 1.6
    lo, hi = 1e5, 5e7
    if NL <= hi:
        return 1.6 * (NL / lo) ** (math.log(1.0 / 1.6) / math.log(hi / lo))
    return (NL / hi) ** (math.log(0.85) / math.log(1e10 / hi))   # conservative branch

def Y_NT(NL, kind, static=False):
    top = 2.5 if kind == "case" else 2.5
    if static or NL <= 1e3:
        return top
    if NL <= 3e6:
        return top * (NL / 1e3) ** (math.log(1.0 / top) / math.log(3e6 / 1e3))
    return (NL / 3e6) ** (math.log(0.85) / math.log(1e10 / 3e6))

# lubricant: ISO VG 220 base oil (grease-lubricated servo gearbox), ground flanks Rz ~ 3 um
NU40 = 220
def lube_factors(v, sHlim):
    CZL = 0.83 if sHlim < 850 else (0.91 if sHlim > 1200 else sHlim / 4375 + 0.6357)
    ZL = CZL + 4 * (1 - CZL) / (1.2 + 134 / NU40) ** 2
    CZV = CZL + 0.02
    ZV = CZV + 2 * (1 - CZV) / math.sqrt(0.8 + 32 / v)
    ZR = 1.0
    return ZL, ZV, ZR

# ---------------------------------------------------------------------------
# 5. Contact / bending for one mesh
# ---------------------------------------------------------------------------
ZE = 189.8
ZH = math.sqrt(2 * math.cos(alpha) / (math.cos(alpha)**2 * math.sin(alpha)))
K1_ISO6, K2 = 14.9, 0.0193        # ISO 6336-1 method C, spur, ISO 1328 grade 6
KHB = 1.15                        # assumed (well-supported pins, b/d1 = 0.56)
hh = haP + hfP
NF_exp = (b / hh)**2 / (1 + b / hh + (b / hh)**2)
KFB = KHB ** NF_exp
KHA = KFA = 1.0

def Kv(Ft, v, u, KA):
    load = max(KA * Ft / b, 100.0)
    return 1 + (K1_ISO6 / load + K2) * (zs * v / 100) * math.sqrt(u**2 / (1 + u**2))

def stage_speeds(n_sun):
    n_c = n_sun / I_STAGE
    n_s_rel = n_sun - n_c
    n_p_rel = n_s_rel * zs / zp
    return dict(n_sun=n_sun, n_carrier=n_c, n_sun_rel=n_s_rel, n_planet_rel=n_p_rel)

def check_stage(T_sun, n_sun, KA, static=False):
    sp = stage_speeds(n_sun)
    Ft = 2000 * T_sun / (d(zs) * N_PL) * K_GAMMA          # N, per planet mesh
    v = pi * d(zs) * sp["n_sun_rel"] / 60000                # m/s, relative to carrier
    u_sp, u_pr = zp / zs, zr / zp
    kv = Kv(Ft, v, u_sp, KA)
    # load cycles over life
    N_sun = 60 * L_H * sp["n_sun_rel"] * N_PL
    N_pl = 60 * L_H * sp["n_planet_rel"]
    N_ring = 60 * L_H * sp["n_carrier"] * N_PL
    res = dict(T_sun=T_sun, Ft_per_mesh=Ft, v=v, Kv=kv, N_sun=N_sun, N_planet=N_pl, N_ring=N_ring, **sp)

    K_H = KA * kv * KHB * KHA
    K_F = KA * kv * KFB * KFA
    hs, hp = MAT[SUN_PLANET_MAT], MAT[RING_MAT]

    # --- contact, sun-planet (external) ---
    Zeps_sp = math.sqrt((4 - eps_sp) / 3)
    sH_sp = ZH * ZE * Zeps_sp * math.sqrt(Ft / (d(zs) * b) * (u_sp + 1) / u_sp) * math.sqrt(K_H)
    # --- contact, planet-ring (internal), referenced to the planet ---
    Zeps_pr = math.sqrt((4 - eps_pr) / 3)
    sH_pr = ZH * ZE * Zeps_pr * math.sqrt(Ft / (d(zp) * b) * (u_pr - 1) / u_pr) * math.sqrt(K_H)

    def sHP(mat, NL, v_):
        ZL, ZV, ZR = lube_factors(v_, mat["sHlim"])
        return mat["sHlim"] * Z_NT(NL, mat["kind"], static) * ZL * ZV * ZR

    res["contact"] = {
        "sun-planet": dict(sigma_H=sH_sp, sigma_HG_sun=sHP(hs, N_sun, v), S_H=sHP(hs, N_sun, v) / sH_sp,
                            S_H_planet=sHP(hs, N_pl, v) / sH_sp),
        "planet-ring": dict(sigma_H=sH_pr, S_H_ring=sHP(hp, N_ring, v) / sH_pr,
                             S_H_planet=sHP(hs, N_pl, v) / sH_pr),
    }

    # --- bending ---
    ff_sun = form_factors(zs, eps_sp)
    ff_pl_s = form_factors(zp, eps_sp)
    ff_pl_r = form_factors(zp, eps_pr)
    ff_ring = form_factors(1000, eps_pr)       # rack bound for the internal ring
    def sigF(ff, eps):
        # ISO 6336-3:2006 method B: YF is taken at the outer point of single-pair contact,
        # so the contact-ratio factor Y_eps is NOT applied (it belonged to the 1996 edition).
        return Ft / (b * m) * ff["YF"] * ff["YS"] * K_F
    def sFP(mat, NL, YM=1.0):
        return mat["sFlim"] * 2.0 * Y_NT(NL, mat["kind"], static) * YM
    sF_sun = sigF(ff_sun, eps_sp)
    sF_pl = max(sigF(ff_pl_s, eps_sp), sigF(ff_pl_r, eps_pr))
    sF_ring = sigF(ff_ring, eps_pr)
    # planet is an idler: reversed bending -> mean-stress factor Y_M = 0.7 (ISO 6336-3/5);
    # a planet tooth is bent once per mesh, twice per revolution.
    res["bending"] = {
        "sun": dict(YF=ff_sun["YF"], YS=ff_sun["YS"], sigma_F=sF_sun, S_F=sFP(hs, N_sun) / sF_sun),
        "planet": dict(YF=ff_pl_s["YF"], YS=ff_pl_s["YS"], sigma_F=sF_pl, S_F=sFP(hs, 2 * N_pl, 0.7) / sF_pl),
        "ring": dict(YF=ff_ring["YF"], YS=ff_ring["YS"], sigma_F=sF_ring, S_F=sFP(hp, N_ring) / sF_ring),
    }
    return res

# ---------------------------------------------------------------------------
# 6. Planet bearing (HK1212) and planet pin
# ---------------------------------------------------------------------------
HK = dict(name="HK1212 (drawn cup needle)", d=12, D=18, B=12, Cr=6270, C0r=7300)  # lowest catalog values
def planet_bearing(T_sun, n_sun, static=False):
    Ft = 2000 * T_sun / (d(zs) * N_PL) * K_GAMMA
    Fr = 2 * Ft                       # tangential forces from sun and ring add on the planet
    sp = stage_speeds(n_sun)
    out = dict(Fr=Fr)
    if static:
        out["S0"] = HK["C0r"] / Fr
    else:
        P = Fr * K_A
        L10 = (HK["Cr"] / P) ** (10 / 3)          # million revolutions, roller bearing
        out.update(P=P, L10_Mrev=L10, L10h=L10 * 1e6 / (60 * sp["n_planet_rel"]))
    return out

PLATE_T = {"stage1": 4.0, "stage2": 6.0}        # carrier plate thickness, mm (CAD)
PLANET_PLATE_GAP = 0.5                           # axial gap planet face -> plate face, each side (CAD)
PIN = dict(d=12.0)
# support span between plate mid-planes = face width + 2 gaps + one plate thickness
PIN_SPAN = {k: b + 2 * PLANET_PLATE_GAP + t for k, t in PLATE_T.items()}
PIN_MAT = dict(name="100Cr6 hardened 60 HRC (needle raceway)", Rp02=1650)
def planet_pin(T_sun, span):
    Fr = 2 * 2000 * T_sun / (d(zs) * N_PL) * K_GAMMA
    M = Fr * span / 4                              # point load at mid-span, simply supported
    sig_b = 32 * M / (pi * PIN["d"]**3)
    tau = 4 / 3 * (Fr / 2) / (pi * PIN["d"]**2 / 4)
    E = 210e3; I = pi * PIN["d"]**4 / 64
    defl = Fr * span**3 / (48 * E * I)
    sig_vm = math.sqrt(sig_b**2 + 3 * tau**2)
    return dict(span=span, Fr=Fr, M_Nmm=M, sigma_b=sig_b, tau=tau, sigma_vm=sig_vm,
                S=PIN_MAT["Rp02"] / sig_vm, deflection_um=defl * 1000)

# ---------------------------------------------------------------------------
# 7. Efficiency (mesh losses, Ohlendorf + Wolf/Kudryavtsev for planetaries)
# ---------------------------------------------------------------------------
MU = 0.05
def Hv(z1, z2, eps, internal=False):
    u = z2 / z1
    e1 = e2 = eps / 2               # approach/recess split assumed equal (x = 0)
    sgn = -1 if internal else 1
    return pi * (u + sgn) / (z1 * u) * (1 - eps + e1**2 + e2**2)
eta_sp = 1 - MU * Hv(zs, zp, eps_sp)
eta_pr = 1 - MU * Hv(zp, zr, eps_pr, internal=True)
eta0 = eta_sp * eta_pr               # basic efficiency, carrier held
i0 = -zr / zs
eta_stage_mesh = (1 - i0 * eta0) / (1 - i0)
ETA_BEARINGS_SEALS = 0.99
eta_stage = eta_stage_mesh * ETA_BEARINGS_SEALS


# ---------------------------------------------------------------------------
# 8. Output: external loads, tapered roller bearings, output shaft (step 4)
# ---------------------------------------------------------------------------
N_OUT = MOTOR["n_rated"] / I_TOTAL
# lowest catalogue values found (SKF/NTN/FAG); e, Y, Y0 from NTN 32006X
TRB = dict(name="32006 X (tapered roller, O arrangement)", d=30, D=55, T=17,
           Cr=35800, C0r=44000, e=0.43, Y=1.4, Y0=0.8)
PC_OFFSET = (TRB["d"] + TRB["D"]) * TRB["e"] / 6       # pressure centre beyond roller centre, mm
MIDPLANES = TRB["T"] + 10.0                            # 10 mm spacer between the cones
L_SPAN = MIDPLANES + 2 * PC_OFFSET                     # effective spread, O arrangement
X_LOAD = 20.0                                          # load at mid-length of a 40 mm shaft extension
# CAD layout (outboard of the front cone): KM6 locknut + MB6 washer (8 mm), d28 seal land (7 mm).
# Diameters only step DOWN toward the free end, so both cones slide on from the output side.
SHOULDER_TO_MID = 15.0 + TRB["T"] / 2
X_OVER = X_LOAD + SHOULDER_TO_MID - PC_OFFSET          # load point -> front pressure centre
AXIAL_RATIO = 0.5                                      # F2a = 0.5 * F2r (servo-gearbox convention)

SHAFT_MAT = dict(name="42CrMo4 +QT (16 < d <= 40 mm, EN 10083-3)", Rm=1000, Re=750)
SIGMA_N = 0.5 * SHAFT_MAT["Rm"] * 0.85 * 0.90           # rotating-bending endurance x size x surface
SHAFT_SECTIONS = {
    "extension shoulder, d25 (fillet r1)": dict(d=25.0, arm=X_LOAD, beta_b=1.8, beta_t=1.4),
    "front bearing seat, d30": dict(d=30.0, arm=X_OVER, beta_b=1.6, beta_t=1.3),
}
S_SHAFT_FAT_MIN = 2.0      # simplified fatigue method (not full DIN 743), so higher than R-016


def tapered_pair(Fr1, Fr2, Ka):
    """Axial split for a pair of tapered bearings; Ka acts in the sense that loads bearing 1."""
    Y = TRB["Y"]
    Fi1, Fi2 = 0.5 * Fr1 / Y, 0.5 * Fr2 / Y
    if Fi2 + Ka >= Fi1:
        return Fi2 + Ka, Fi2
    return Fi1, Fi1 - Ka


def trb_P(Fr, Fa):
    return Fr if Fa / Fr <= TRB["e"] else 0.4 * Fr + TRB["Y"] * Fa


def output_check(F2r, F2a=None):
    F2a = AXIAL_RATIO * F2r if F2a is None else F2a
    RA = F2r * (L_SPAN + X_OVER) / L_SPAN                 # front bearing
    RB = F2r * X_OVER / L_SPAN                            # rear bearing
    worst_L10h, worst_S0 = 1e30, 1e30
    detail = {}
    for sense in ("axial_load_on_front", "axial_load_on_rear"):
        if sense == "axial_load_on_front":
            FaA, FaB = tapered_pair(RA, RB, F2a)
        else:
            FaB, FaA = tapered_pair(RB, RA, F2a)
        for name, Fr, Fa in (("front", RA, FaA), ("rear", RB, FaB)):
            P = trb_P(Fr, Fa) * K_A
            L10h = (TRB["Cr"] / P) ** (10 / 3) * 1e6 / (60 * N_OUT)
            P0 = max(Fr, 0.5 * Fr + TRB["Y0"] * Fa)
            S0 = TRB["C0r"] / P0
            detail[f"{sense}/{name}"] = dict(Fr=Fr, Fa=Fa, P=P, L10h=L10h, P0=P0, S0=S0)
            worst_L10h, worst_S0 = min(worst_L10h, L10h), min(worst_S0, S0)
    shaft = {}
    T_fat = T2N * K_A * 1000      # N.mm, steady mean torque
    T_peak = T2B * 1000
    for name, sec in SHAFT_SECTIONS.items():
        dd = sec["d"]
        Wb, Wt, A = pi * dd**3 / 32, pi * dd**3 / 16, pi * dd**2 / 4
        M = F2r * sec["arm"]
        sig_a = sec["beta_b"] * M / Wb                    # rotating bending, fully reversed
        sig_m = F2a / A
        tau_m = sec["beta_t"] * T_fat / Wt
        sig_m_eq = math.sqrt(sig_m**2 + 3 * tau_m**2)
        S_fat = 1 / (sig_a / SIGMA_N + sig_m_eq / SHAFT_MAT["Rm"])      # Goodman
        sig_st = M / Wb + F2a / A
        tau_st = T_peak / Wt
        S_st = SHAFT_MAT["Re"] / math.sqrt(sig_st**2 + 3 * tau_st**2)
        shaft[name] = dict(M_Nmm=M, sigma_a=sig_a, tau_m=tau_m, S_fatigue=S_fat,
                           tau_peak=tau_st, S_static=S_st)
    return dict(F2r=F2r, F2a=F2a, R_front=RA, R_rear=RB, L10h_min=worst_L10h, S0_min=worst_S0,
                bearings=detail, shaft=shaft,
                S_fat_min=min(v["S_fatigue"] for v in shaft.values()),
                S_st_min=min(v["S_static"] for v in shaft.values()))


def max_F2r(key, target):
    lo, hi = 10.0, 50000.0
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if output_check(mid)[key] > target else (lo, mid)
    return lo


F2R_LIMITS = {
    "bearing life L10h >= 10000 h": max_F2r("L10h_min", L_H),
    "bearing static S0 >= 2": max_F2r("S0_min", S0_MIN),
    "shaft fatigue S >= 2.0": max_F2r("S_fat_min", S_SHAFT_FAT_MIN),
    "shaft static S >= 1.5": max_F2r("S_st_min", SF_STAT_MIN),
}
F2R_RATED = 3000.0          # chosen catalogue rating (rounded down from the governing limit)
F2A_RATED = 1500.0
OUTPUT_RATED = output_check(F2R_RATED, F2A_RATED)
M2K = F2R_RATED * (X_OVER + L_SPAN / 2) / 1000        # tilting moment about the bearing-pair centre, N.m

# ---------------------------------------------------------------------------
# 9. Input: shaft d12 (integral with sun 1), 2 x 6201, bellows coupling
# ---------------------------------------------------------------------------
DGBB = dict(name="6201-2Z (12x32x10)", Cr=7280, C0r=3100)
F_IN_RADIAL = 200.0        # per bearing: coupling restoring force + weight, generous assumption


def input_check():
    P = F_IN_RADIAL * K_A
    L10h = (DGBB["Cr"] / P) ** 3 * 1e6 / (60 * MOTOR["n_rated"])
    d_in = 12.0
    tau_peak = 16 * MOTOR["T_peak"] * 1000 / (pi * d_in**3)
    seal_v = pi * d_in * MOTOR["n_max"] / 60000
    T_coupling_min = MOTOR["T_peak"] * 1.5
    return dict(L10h=L10h, tau_peak=tau_peak, S_static=SHAFT_MAT["Re"] / (math.sqrt(3) * tau_peak),
                seal_surface_speed=seal_v, coupling_rated_torque_min=T_coupling_min,
                sun_root_over_shaft=m * (zs - 2.5) / d_in)

# ---------------------------------------------------------------------------
# 10. ISO 286 fits (deviations in micrometres; bearing rings to ISO 492 normal class)
# ---------------------------------------------------------------------------
FITS = [
    # (joint, nominal, hole, hole (ES, EI), shaft, shaft (es, ei), reason)
    ("32006 X cone on output shaft", 30, "bearing bore", (0, -10), "k6", (15, 2), "rotating inner-ring load"),
    ("32006 X cup in housing", 55, "J7", (18, -12), "bearing OD", (0, -13), "stationary outer-ring load, steel housing"),
    ("HK1212 cup in planet bore", 18, "N6", (-9, -20), "bearing OD", None, "drawn cup: the press fit rounds the cup"),
    ("Planet pin as raceway", 12, "needle set", None, "h6", (0, -11), "running clearance set by the N6 bore"),
    ("Planet pin in bridge plate", 12, "R7", (-16, -34), "h6", (0, -11), "press fit: holds the pin axially, pin does not turn"),
    ("Planet pin in bolted plate", 12, "M6", (-4, -15), "h6", (0, -11), "pin is the dowel of the bolted plate; small play keeps the pin parallel"),
    ("6201 on input shaft", 12, "bearing bore", (0, -8), "j6", (8, -3), "rotating inner ring, light load"),
    ("6201 in input housing", 32, "J7", (14, -11), "bearing OD", (0, -11), "stationary outer ring, one bearing floats axially"),
    ("Output shaft extension", 25, "customer hub", None, "h6", (0, -13), "clamp / shrink-disc hub, keyless"),
]


def fit_range(hole, shaft):
    if hole is None or shaft is None:
        return None
    ES, EI = hole
    es, ei = shaft
    return dict(max_clearance=ES - ei, max_interference=es - EI)


FITS_OUT = [dict(joint=j, nominal=n, hole=h, hole_dev=hd, shaft=sh, shaft_dev=sd, reason=r,
                 range_um=fit_range(hd, sd)) for j, n, h, hd, sh, sd, r in FITS]

# ---------------------------------------------------------------------------
# 11. Interstage connection and carriers (step 5)
#     The stage 2 sun is a separate shaft-gear with an integral DIN 5480 spline stub that
#     is pressed (interference spline fit, no backlash) into a hub on the stage 1 rear
#     carrier plate. Carriers are cages: plate + 3 bridges between the planets, the
#     opposite plate screwed and dowelled to the bridges.
# ---------------------------------------------------------------------------
SPLINE = dict(name="DIN 5480 W 16 x 1 x 14", dB=16.0, m=1.0, z=14, L=8.0, phi=0.75,
              p_allow_static=200.0, p_allow_fatigue=100.0)   # QT hub ~300 HB
SHOULDER_D = 20.0             # axial stop between stub and sun teeth, below d_f = 23.25
def interstage():
    sp = SPLINE
    d_m = sp["m"] * sp["z"]                        # pitch diameter 14 mm
    h_w = 0.9 * sp["m"]                            # load-bearing flank depth
    A_eff = d_m / 2 * h_w * sp["L"] * sp["z"] * sp["phi"]    # mm^3: torque = p * A_eff
    T_nom = MOTOR["T_rated"] * I_STAGE * 1000 * K_A          # N.mm
    T_pk = MOTOR["T_peak"] * I_STAGE * 1000
    p_nom, p_pk = T_nom / A_eff, T_pk / A_eff
    d_root = sp["dB"] - 2.2 * sp["m"]              # approximate root diameter of the shaft spline
    tau_pk = 16 * T_pk / (pi * d_root**3)
    Re_core = 800.0                                # 18CrNiMo7-6 core after case hardening
    return dict(spline=sp["name"], engagement_L=sp["L"], p_rated_KA=p_nom, p_peak=p_pk,
                S_p_fatigue=sp["p_allow_fatigue"] / p_nom, S_p_static=sp["p_allow_static"] / p_pk,
                d_root=d_root, tau_peak_root=tau_pk, S_static_stub=Re_core / (math.sqrt(3) * tau_pk))

# Carrier bridges: three webs in the gaps between planets
PLATE_GAP = 16.0                               # inner faces of the plates are at +/- 8 mm
BRIDGE_T, BRIDGE_H = 10.0, 18.0                # tangential thickness x radial depth, mm
BRIDGE_R = a_w                                 # bridge centroid on the planet-centre circle
def bridge_planet_clearance():
    """Smallest gap between a bridge (rectangle, mid-way between two planets) and a planet tip circle."""
    phi = pi / N_PL                                   # angle bridge -> neighbouring planet
    u = a_w * math.cos(phi) - BRIDGE_R               # planet centre in bridge axes (u radial, w tangential)
    w = a_w * math.sin(phi)
    du = max(abs(u) - BRIDGE_H / 2, 0.0)
    dw = max(abs(w) - BRIDGE_T / 2, 0.0)
    return math.hypot(du, dw) - (d(zp) / 2 + m)
def carrier_bridge(T_carrier_Nm):
    # half of every planet force reaches the far plate and must come back through the bridges
    V = (T_carrier_Nm * 1000 / 2) / (BRIDGE_R * N_PL)
    M = V * PLATE_GAP / 2                      # guided (fixed-fixed) beam between the plates
    W = BRIDGE_H * BRIDGE_T**2 / 6
    sig = M / W
    tau = 1.5 * V / (BRIDGE_T * BRIDGE_H)
    return dict(V=V, M_Nmm=M, sigma=sig, tau=tau)

CARRIER = dict(
    interstage=interstage(),
    bridge_to_planet_tip_clearance=bridge_planet_clearance(),
    bridge_radial_extent=(BRIDGE_R - BRIDGE_H / 2, BRIDGE_R + BRIDGE_H / 2),
    sun_tip_radius=d(zs) / 2 + m, ring_tip_radius=d(zr) / 2 - m,
    stage1_bridge_peak=carrier_bridge(MOTOR["T_peak"] * I_STAGE),
    stage2_bridge_peak=carrier_bridge(T2B),
)

# ---------------------------------------------------------------------------
# 12. Planet thrust washers, pin retention and mesh misalignment (step 5)
#     Assembly: the cage is bolted first and both pin bores are finished in one set-up.
#     Planets with their washers go in radially between the bridges; each pin is then
#     pressed through the bolted plate (M6) and the bearing into the bridge plate (R7).
# ---------------------------------------------------------------------------
WASHER = dict(d=12.2, D=24.0, t=0.4, mat="1.8159 (51CrV4) hardened and tempered 45-50 HRC")
HK_CUP_RECESS = (b - HK["B"]) / 2                # cup sits 1.5 mm inside each planet face
BORE_CHAMFER = 0.5
FA_SHARE = 0.10                                  # assumed planet thrust = 10 % of Ft (spur: misalignment only)

def thrust_washer():
    end_float = 2 * (PLANET_PLATE_GAP - WASHER["t"])
    r_in = HK["D"] / 2 + BORE_CHAMFER              # washer bears on the planet face outside the cup
    r_out = WASHER["D"] / 2
    A_planet = pi * (r_out**2 - r_in**2)
    out = dict(end_float_total=end_float, contact_annulus_planet=(r_in, r_out), A_planet_mm2=A_planet,
               washer_to_sun_tip=a_w - r_out - (d(zs) / 2 + m),
               washer_inside_planet_root=r_out < m * (zp - 2.5) / 2)
    for stage, T_sun in (("stage1", MOTOR["T_peak"]), ("stage2", MOTOR["T_peak"] * I_STAGE)):
        n_sun = MOTOR["n_max"] / (1 if stage == "stage1" else I_STAGE)
        Ft = 2000 * T_sun / (d(zs) * N_PL) * K_GAMMA
        Fa = FA_SHARE * Ft
        p = Fa / A_planet
        v = 2 * pi * stage_speeds(n_sun)["n_planet_rel"] / 60 * (r_in + r_out) / 2 / 1000
        out[stage + "_peak"] = dict(Fa=Fa, p=p, v_mean=v, pv=p * v)
    return out

E_STEEL, NU_STEEL = 210e3, 0.3
MU_PRESS = 0.10                                  # longitudinal press fit, steel/steel, oiled
SMOOTHING = 0.8 * (1.0 + 4.0)                    # DIN 7190: 0.8 (Rz pin ground + Rz bore reamed), um
PLATE_R = 48.0                                   # carrier plate outer radius (CAD)
def pin_press_fit():
    ES, EI = (-16, -34); es, ei = (0, -11)       # R7 / h6, um
    D_eff = PIN["d"] + 2 * (PLATE_R - a_w - PIN["d"] / 2)   # thinnest ligament taken as a ring
    Q = PIN["d"] / D_eff
    k = (1 + Q**2) / (1 - Q**2)
    C = PIN["d"] * ((k + NU_STEEL) / E_STEEL + (1 - NU_STEEL) / E_STEEL)  # mm per MPa (solid pin)
    res = dict(D_eff_ring=D_eff)
    deltas = dict(min=ei - ES, mean=((es + ei) - (ES + EI)) / 2, max=es - EI)
    for tag, dl in deltas.items():
        de = max(dl - SMOOTHING, 0.0) / 1000      # mm
        p = de / C
        res[tag] = dict(interference_um=dl, p=p, hub_vm=p * math.sqrt(k**2 + k + 1),
                        push_out_stage1=MU_PRESS * p * pi * PIN["d"] * PLATE_T["stage1"],
                        push_out_stage2=MU_PRESS * p * pi * PIN["d"] * PLATE_T["stage2"])
    res["S_hub_max"] = SHAFT_MAT["Re"] / res["max"]["hub_vm"]
    return res

# ISO 1328-1 helix slope deviation, class 5 base formula x sqrt(2) per grade (grade 6)
def f_Hbeta(dia, width, grade=6):
    return (0.07 * math.sqrt(dia) + 0.45 * math.sqrt(width) + 3.0) * math.sqrt(2) ** (grade - 5)

C_GAMMA = 20.0                                   # mesh stiffness, N/(mm.um), solid steel gears
def KHB_methodC(Fm_b, Fbx):
    Fby = 0.85 * Fbx                              # running-in y_beta = 0.15 Fbx (case-hardened)
    cgb = 0.85 * C_GAMMA
    k = 1 + cgb * Fby / (2 * Fm_b)
    return k if k <= 2 else math.sqrt(2 * cgb * Fby / Fm_b)

def misalignment(fit_play_um):
    """Pin tilt from the bolted-plate fit plus helix slope deviation -> K_H_beta and S_H (ISO 6336-1 method C)."""
    global KHB, KFB
    out = {}
    fHb = f_Hbeta(d(zp), b)
    for stage, (T_sun, n_sun) in (("stage1", (MOTOR["T_rated"], MOTOR["n_rated"])),
                                  ("stage2", (MOTOR["T_rated"] * I_STAGE, MOTOR["n_rated"] / I_STAGE))):
        tilt = (fit_play_um / 2) / PIN_SPAN[stage] * b      # um across the face width
        r = check_stage(T_sun, n_sun, K_A)
        Fm_b = r["Ft_per_mesh"] * K_A * r["Kv"] / b
        cases = {}
        for label, B in (("no_modification", 1.0), ("helix_crowning", 0.5)):   # ISO 6336-1 table 8 (B2)
            Fbx = B * math.hypot(fHb, tilt)        # f_sh ~ 0: planet centred on its pin, sun floats
            khb = KHB_methodC(Fm_b, Fbx)
            keep = (KHB, KFB)
            KHB, KFB = khb, khb ** NF_exp
            rr = check_stage(T_sun, n_sun, K_A)
            KHB, KFB = keep
            cases[label] = dict(F_beta_x=Fbx, KHB=khb,
                                S_H_min=min(rr["contact"]["sun-planet"]["S_H"], rr["contact"]["sun-planet"]["S_H_planet"],
                                            rr["contact"]["planet-ring"]["S_H_ring"], rr["contact"]["planet-ring"]["S_H_planet"]),
                                S_F_min=min(v["S_F"] for v in rr["bending"].values()))
        out[stage] = dict(f_Hbeta=fHb, pin_tilt_over_face=tilt, Fm_per_b=Fm_b, **cases)
    return out

PLANETS = dict(
    pin_span=PIN_SPAN,
    washer=WASHER, hk_cup_recess=HK_CUP_RECESS, thrust_washer=thrust_washer(),
    press_fit_R7=pin_press_fit(),
    misalignment_M6=misalignment(-4 - (-11)),    # max play M6/h6: ES_hole - ei_pin
    misalignment_K7=misalignment(6 - (-11)),     # alternative K7/h6, for comparison
)

# ---------------------------------------------------------------------------
# 13. Housing, ring retention and mounting (step 6)
#     Sandwich construction: input housing | ring 1 | spacer | ring 2 | output housing,
#     clamped by axial tie bolts through the ring rims. The rings are the outer wall.
#     z = 0 at the stage 1 mid-plane, output toward -z (CAD coordinates).
# ---------------------------------------------------------------------------
HOUSING_OD = 140.0                              # R-014
TIE = dict(name="ISO 4762 M6x70 - 8.8", n=8, d=6.0, d_h=6.6, d_w=9.38, A_N=28.27, A_3=17.89,
           b_thread=24.0, F_M_tab=10.4e3, M_A=10.1)   # VDI 2230 table A1, mu_G = 0.12, 90 % of Rp0.2
BOLT_PCD = 128.0
ALPHA_A = 1.6                                   # tightening factor, torque wrench
MU_JOINT = 0.15                                 # steel / GJS faces, dry, machined (anaerobic sealant)
S_SLIP_MIN = 1.8                                # reversing servo torque: alternating transverse load
E_GJS = 169e3                                   # EN-GJS-500-7 (EN 1563 typical); SOLIDWORKS library lists 120 GPa
P_G_GJS = 750.0                                 # limiting surface pressure under the head, VDI 2230 table A9
STACK = [("input housing flange", 17.5, E_GJS), ("ring 1", b, E_STEEL),
         ("interstage spacer", 12.0, E_STEEL), ("ring 2", b, E_STEEL)]   # clamped parts, head side first
N_INTERFACES = 4                                # input|ring1, ring1|spacer, spacer|ring2, ring2|output
F_Z_UM = 3.0 + 3.0 + 2.0 * N_INTERFACES        # VDI 2230 table 5, Rz < 10 um, transverse load
RIM_SECTOR_R = (56.0, HOUSING_OD / 2)           # clamped annulus between ring root and OD

def tie_bolts():
    l_K = sum(l for _, l, _ in STACK)
    l_shank = 70.0 - TIE["b_thread"]
    l_thread_free = l_K - l_shank
    d6 = TIE["d"]
    delta_S = (0.5 * d6 / TIE["A_N"] + l_shank / TIE["A_N"] + l_thread_free / TIE["A_3"]
               + 0.5 * d6 / TIE["A_3"] + 0.33 * d6 / TIE["A_N"]) / 205e3     # tapped joint (ESV)
    r_i, r_o = RIM_SECTOR_R
    A_ers = pi * (r_o**2 - r_i**2) / TIE["n"] - pi / 4 * TIE["d_h"]**2      # long grip: the sector carries it
    delta_P = sum(l / E for _, l, E in STACK) / A_ers
    F_Z = F_Z_UM / 1000 / (delta_S + delta_P)
    F_V_min = TIE["F_M_tab"] / ALPHA_A - F_Z
    clamp = TIE["n"] * F_V_min
    r = BOLT_PCD / 2
    T_slip = MU_JOINT * clamp * r / 1000                                     # N.m per joint
    Tin = MOTOR["T_peak"]
    joints = {  # torque each joint carries at peak (motor stator + ring reactions, all the same sign)
        "input housing | ring 1": Tin,
        "ring 1 | spacer | ring 2": Tin * I_STAGE,
        "ring 2 | output housing": Tin * I_TOTAL,
    }
    A_p = pi / 4 * (TIE["d_w"]**2 - TIE["d_h"]**2)
    s_R = BOLT_PCD / 2 - TIE["d_h"] / 2 - m * (zr + 2.5) / 2
    return dict(bolt=TIE["name"], n=TIE["n"], pcd=BOLT_PCD, l_K=l_K, delta_S=delta_S, delta_P=delta_P,
                load_factor_Phi=delta_P / (delta_S + delta_P), f_Z_um=F_Z_UM, F_Z=F_Z,
                F_V_min=F_V_min, clamp_total=clamp, T_slip_per_joint=T_slip,
                joints={k: dict(T_peak=v, S_slip=T_slip / v) for k, v in joints.items()},
                head_pressure=TIE["F_M_tab"] / A_p, S_head=P_G_GJS / (TIE["F_M_tab"] / A_p),
                thread_engagement=11.5 - 1.0, ring_rim_at_hole=s_R, ring_rim_min=1.2 * 2.25 * m,
                ring_outer_ligament=HOUSING_OD / 2 - (BOLT_PCD / 2 + TIE["d_h"] / 2),
                tightening_torque=TIE["M_A"])

# Mounting: 4 x M8 - 10.9 tapped through the output flange, face at z = -46, spigot = bearing neck d80 h7
MOUNT = dict(n=4, name="ISO 4762 M8 - 10.9", F_M_tab=28.0e3, pcd=BOLT_PCD, z_face=-46.0,
             spigot_d=80.0, spigot_bore=55.0)
Z_LOAD = -123.0                                 # F2r at mid-length of the d25 extension (z -103 ... -143)
def mounting():
    F_V = MOUNT["F_M_tab"] / ALPHA_A * 0.9      # 10 % embedding loss (short grip in the customer plate)
    r = MOUNT["pcd"] / 2
    lever = MOUNT["z_face"] - Z_LOAD
    M_tilt = F2R_RATED * lever / 1000           # N.m at the mounting face
    F_A_max = 2 * M_tilt * 1000 / (MOUNT["n"] * r) + F2A_RATED / MOUNT["n"]
    F_t = T2B * 1000 / (MOUNT["n"] * r)         # torque only: the spigot takes the radial load F2r
    S_slip = MU_JOINT * (F_V - F_A_max) / F_t
    D, d_i = MOUNT["spigot_d"], MOUNT["spigot_bore"]
    W_b = pi * (D**4 - d_i**4) / (32 * D)
    sigma_neck = M_tilt * 1000 / W_b
    tau_neck = T2B * 1000 / (2 * W_b)
    return dict(bolts=MOUNT["name"], n=MOUNT["n"], F_V_min=F_V, lever=lever, M_tilt=M_tilt,
                F_A_max_per_bolt=F_A_max, F_t_per_bolt_peak=F_t, S_slip=S_slip,
                no_separation=F_V > F_A_max, neck_sigma_b=sigma_neck, neck_tau=tau_neck,
                thread_engagement_over_d=11.5 / 8.0)

# Layout chain on the input side (step 6 CAD) and overall length (R-015)
INPUT_SIDE = dict(shaft_end=75.0, coupling_gearbox_hub=(55.0, 75.0), motor_shaft_LR=40.0,
                  motor_face=125.0, motor_spigot="d70 h7", motor_pcd=90.0, motor_bolts="4 x M6")
L_OVERALL = INPUT_SIDE["motor_face"] - MOUNT["z_face"]    # mounting face to motor face

# Heat balance at the rated point (continuous operation at 3000 rpm)
ALPHA_HEAT = 15.0                              # W/(m2 K): natural convection ~9 + radiation ~6 (painted)
P_EXTRA = 10.0                                 # W: input seal at 3000 rpm, bearings, grease churning (estimate)
def heat_balance():
    P_in = MOTOR["T_rated"] * MOTOR["n_rated"] * 2 * pi / 60
    P_loss = P_in * (1 - eta_stage**2) + P_EXTRA
    A = (pi * HOUSING_OD * 71                                   # d140 band, z -46 ... +25
         + 2 * pi / 4 * (HOUSING_OD**2 - 80.0**2)               # flange faces
         + pi * 80 * 50 + pi / 4 * 80**2                        # output neck and end
         + pi * 80 * 75 + pi * 106 * 12 + pi / 4 * (106**2 - 80**2)) / 1e6   # motor adapter
    P_loss_pess = P_in * (1 - 0.95**2)          # requirements-sheet bound, 0.95 per stage
    return dict(P_in=P_in, P_loss=P_loss, A_m2=A, alpha=ALPHA_HEAT, dT=P_loss / (ALPHA_HEAT * A),
                P_loss_pessimistic=P_loss_pess, dT_pessimistic=P_loss_pess / (ALPHA_HEAT * A))

# Carrier cage screws (step 7): one M5 - 8.8 per bridge clamps the bolted plate to the bridge.
# The bridge shear V (section 11) must cross that joint, by friction or through the pins,
# which are the dowels of the bolted plate (M6 / h6, D-024).
CAGE_SCREW = dict(name="M5 - 8.8 (ISO 4762 stage 1, DIN 7984 stage 2)", F_M_tab=6.9e3, M_A=5.9)
def cage_screws():
    F_V = CAGE_SCREW["F_M_tab"] / ALPHA_A * 0.9           # 10 % embedding, short grip
    cap = MU_JOINT * F_V
    out = dict(screw=CAGE_SCREW["name"], F_V_min=F_V, friction_capacity=cap)
    for st in ("stage1", "stage2"):
        V = CARRIER[st + "_bridge_peak"]["V"]
        V_rated = V * MOTOR["T_rated"] * K_A / MOTOR["T_peak"]   # fatigue case, K_A included
        out[st] = dict(V_peak=V, S_slip_friction_only=cap / V, V_rated_KA=V_rated, S_slip_rated=cap / V_rated,
                       pin_shear_if_slip=V / (pi / 4 * PIN["d"] ** 2))   # MPa in one pin, worst case
    return out

HOUSING = dict(
    concept="ring gears as housing sections, clamped by tie bolts",
    od=HOUSING_OD, ring_od_old=126.5,
    materials=dict(input_housing="0.7050 (EN-GJS-500-7)", output_housing="0.7050 (EN-GJS-500-7)",
                   spacer="1.0503 (C45)", seal_cover="1.0503 (C45)"),
    tie_bolts=tie_bolts(), mounting=mounting(), heat=heat_balance(), cage_screws=cage_screws(),
    input_side=INPUT_SIDE, L_overall=L_OVERALL,
    ring_torque_peak=dict(stage1=MOTOR["T_peak"] * (I_STAGE - 1), stage2=MOTOR["T_peak"] * I_STAGE * (I_STAGE - 1)),
    al_alternative=dict(radial_slip_at_pcd_60K=BOLT_PCD / 2 * (23e-6 - 11.5e-6) * 60),
)

# ---------------------------------------------------------------------------
# 14. Backlash, tooth thickness, inspection dimensions, crowning, tolerance stacks (step 8)
# ---------------------------------------------------------------------------
# ISO 1328-1 grade 6: single pitch deviation (class-5 base formula x sqrt(2) per grade)
def f_pt(dia, grade=6):
    return (0.3 * (m + 0.4 * math.sqrt(dia)) + 4.0) * math.sqrt(2) ** (grade - 5)

# Tooth thickness allowances (normal, um): upper E_sns / lower E_sni. For the ring (internal
# teeth) a negative allowance thins the tooth, i.e. widens the space, which also adds backlash.
TOOTH_ALLOW = {"sun": (-15, -35), "planet": (-20, -40), "ring": (-15, -35)}
F_A_POS = 8.0              # um: planet-centre radial position from the pin-bore position tolerance (dia 0.016)
J_LUBE = 10.0              # um: minimum running clearance for the grease film
DT_GEAR_CARRIER = 10.0     # K: gears warmer than the carrier (same steels otherwise)

def backlash():
    fpt_s, fpt_p, fpt_r = f_pt(d(zs)), f_pt(d(zp)), f_pt(d(zr))
    fhb = f_Hbeta(d(zp), b)
    cosa, sina = math.cos(alpha), math.sin(alpha)
    j_thermal = 2 * a_w * 11.5e-6 * DT_GEAR_CARRIER * sina * 1000      # um
    meshes = {"sun-planet": ("sun", "planet", fpt_s), "planet-ring": ("planet", "ring", fpt_r)}
    out = dict(f_pt=dict(sun=fpt_s, planet=fpt_p, ring=fpt_r), f_Hbeta=fhb, allowances_um=TOOTH_ALLOW,
               j_thermal=j_thermal, j_lube=J_LUBE, f_a_pos=F_A_POS)
    jt = {}
    for name, (g1, g2, fpt1) in meshes.items():
        J_n = math.sqrt(fpt1**2 + fpt_p**2 + 2 * (fhb * sina) ** 2)   # deviation effect (RSS), um
        req = J_LUBE + J_n + j_thermal + 2 * F_A_POS * sina             # backlash the allowances must provide
        jn_min = -(TOOTH_ALLOW[g1][0] + TOOTH_ALLOW[g2][0]) * cosa - J_n - 2 * F_A_POS * sina - j_thermal
        jn_max = -(TOOTH_ALLOW[g1][1] + TOOTH_ALLOW[g2][1]) * cosa + 2 * F_A_POS * sina
        out[name] = dict(J_n=J_n, required_from_allowances=req,
                         from_allowances_min=-(TOOTH_ALLOW[g1][0] + TOOTH_ALLOW[g2][0]) * cosa,
                         jn_min_running=jn_min, jn_max=jn_max, jn_mean=(jn_min + jn_max) / 2)
        jt[name] = (jn_min / cosa, jn_max / cosa)
    # carrier play with input and ring locked: delta = (j_t,sp + j_t,pr) / (2 a)
    am = 180 * 60 / pi
    phi_min = (jt["sun-planet"][0] + jt["planet-ring"][0]) / (2 * a_w * 1000) * am
    phi_max = (jt["sun-planet"][1] + jt["planet-ring"][1]) / (2 * a_w * 1000) * am
    out["stage_carrier_play_arcmin"] = (phi_min, phi_max)
    out["output_backlash_arcmin"] = (phi_min * (1 + 1 / I_STAGE), phi_max * (1 + 1 / I_STAGE))
    # RSS estimate: allowances uniform within their band -> sigma = T/sqrt(12) per gear
    T = {k: (v[0] - v[1]) for k, v in TOOTH_ALLOW.items()}
    def mesh_rss(g1, g2):
        mean = -((TOOTH_ALLOW[g1][0] + TOOTH_ALLOW[g1][1]) / 2 + (TOOTH_ALLOW[g2][0] + TOOTH_ALLOW[g2][1]) / 2) * cosa
        sig = math.sqrt((T[g1] * cosa) ** 2 / 12 + (T[g2] * cosa) ** 2 / 12 + (2 * F_A_POS * sina) ** 2 / 12)
        return mean, sig
    (m1, s1), (m2, s2) = mesh_rss("sun", "planet"), mesh_rss("planet", "ring")
    phi_mean = (m1 + m2) / cosa / (2 * a_w * 1000) * am * (1 + 1 / I_STAGE)
    phi_3s = math.hypot(s1, s2) * 3 / cosa / (2 * a_w * 1000) * am * (1 + 1 / I_STAGE)
    out["output_backlash_rss_arcmin"] = (phi_mean - phi_3s, phi_mean + phi_3s)
    return out

def span_and_pins(D_ball=2.5):
    """Base tangent length W_k (external) and dimension over / between balls, nominal and with allowances (mm)."""
    cosa = math.cos(alpha)
    res = {}
    for gear, z in (("sun", zs), ("planet", zp), ("ring", zr)):
        hi, lo = TOOTH_ALLOW[gear]
        dg, dbg = d(z), db(z)
        row = dict(z=z, d=dg, d_b=dbg, ball=D_ball)
        if gear != "ring":
            k = math.floor(z * alpha / pi + 0.5)          # z/9 + 0.5, truncated: 18 -> 2, 27 -> 3 (DIN 3960 tables)
            W = m * cosa * (pi * (k - 0.5) + z * inv(alpha))
            row.update(k=k, W_k=W, W_k_upper=W + hi / 1000 * cosa, W_k_lower=W + lo / 1000 * cosa)
        def M(e_um):
            s = pi * m / 2 + e_um / 1000                     # tooth thickness (ext) / space width (int) at d
            if gear == "ring":
                s = pi * m / 2 - e_um / 1000                 # thinner ring teeth -> wider space
                invM = s / dg + inv(alpha) - D_ball / dbg
            else:
                invM = s / dg + inv(alpha) + D_ball / dbg - pi / z
            aM = 0.6
            for _ in range(60):
                aM -= (inv(aM) - invM) / (math.tan(aM) ** 2)
            dM = dbg / math.cos(aM)
            if gear == "ring":
                return dM - D_ball                           # z even: between balls
            return (dM if z % 2 == 0 else dM * math.cos(pi / (2 * z))) + D_ball
        row.update(M_nominal=M(0), M_upper=M(hi), M_lower=M(lo))
        res[gear] = row
    return res

def crowning():
    """Helix crowning on the planets (D-025): parabolic, height C_b across the face width."""
    fhb = f_Hbeta(d(zp), b)
    tilt = (7 / 2) / PIN_SPAN["stage2"] * b
    Fbx0 = math.hypot(fhb, tilt)
    C_b = 5.0                                              # um, specified (tolerance 3 ... 7)
    r = check_stage(MOTOR["T_rated"] * I_STAGE, MOTOR["n_rated"] / I_STAGE, K_A)
    Fm_b = r["Ft_per_mesh"] * K_A * r["Kv"] / b
    defl = Fm_b / (0.85 * C_GAMMA)                         # mesh deflection at the rated load, um
    contact = min(1.0, math.sqrt(defl / C_b))              # loaded fraction of the face (centred contact)
    rp = check_stage(MOTOR["T_peak"] * I_STAGE, 0.1, 1.0, True)
    defl_pk = rp["Ft_per_mesh"] / b / (0.85 * C_GAMMA)
    return dict(F_bx_unmodified=Fbx0, C_b=C_b, C_b_tol=(3.0, 7.0), C_b_min_to_keep_contact_central=Fbx0 / 4,
                mesh_deflection_rated=defl, contact_width_fraction_rated=contact,
                mesh_deflection_peak=defl_pk, contact_width_fraction_peak=min(1.0, math.sqrt(defl_pk / C_b)))

def tolerance_stacks():
    st = {}
    # planet end float: cage gap 16 (bridge length) - planet width - 2 washers
    gap, gap_t = 16.0, (0.02, -0.02); w, w_t = 15.0, (0.0, -0.027); t, t_t = 0.4, (0.02, -0.02)
    st["planet_end_float"] = dict(nominal=gap - w - 2 * t,
                                  min=(gap + gap_t[1]) - (w + w_t[0]) - 2 * (t + t_t[0]),
                                  max=(gap + gap_t[0]) - (w + w_t[1]) - 2 * (t + t_t[1]),
                                  spec="bridge 16 +/-0.02, planet width 15 h8, washer 0.4 +/-0.02")
    # input bearings, cross-located: shaft shoulder-to-groove 30 +0.1/0, 6201 width 10 0/-0.12, collar 10 -0.05/-0.10
    st["input_axial_play"] = dict(min=30.0 - (10 + 10 + 9.95), max=30.10 - (9.88 + 9.88 + 9.90),
                                  spec="shaft 30 +0.10/0, collar 10 -0.05/-0.10, 6201 B 10 0/-0.12")
    # output bearings: spacer ground on assembly to the measured collar + bearing stand-out
    st["output_bearing_setting"] = dict(target_axial_um=(0, 10), method="measure cups on the collar, grind the cone spacer")
    # axial offset ring 2 vs stage 2 planets (ring stack + carrier on its bearings)
    chain = {"output housing collar face to ring seat": 0.03, "ring 2 width": 0.02, "carrier shoulder to pin mid-plane": 0.05,
             "bearing stand-out after setting": 0.05, "planet float (half)": 0.15}
    wc = sum(chain.values()); rss = math.sqrt(sum(v * v for v in chain.values()))
    st["ring2_planet_axial_offset"] = dict(contributors_mm=chain, worst_case=wc, rss=rss, b_eff_min=b - wc)
    return st

STEP8 = dict(backlash=backlash(), inspection=span_and_pins(), crowning=crowning(), stacks=tolerance_stacks())

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
cases = {}
for name, Tin, KA, static in [("fatigue_rated", MOTOR["T_rated"], K_A, False),
                              ("static_peak", MOTOR["T_peak"], 1.0, True)]:
    s1 = check_stage(Tin, MOTOR["n_rated"], KA, static)
    s2 = check_stage(Tin * I_STAGE, MOTOR["n_rated"] / I_STAGE, KA, static)
    cases[name] = {"stage1": s1, "stage2": s2}

# ---------------------------------------------------------------------------
# Rating: largest nominal output torque each criterion allows (stage 2 governs)
# ---------------------------------------------------------------------------
def solve_T2(fn, target):
    lo, hi = 1.0, 2000.0
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if fn(mid) > target else (lo, mid)
    return lo
def _st2(T2):
    return check_stage(T2 / I_STAGE, MOTOR["n_rated"] / I_STAGE, K_A)
rating = {
    "contact_sun_planet (S_H=1.2)": solve_T2(lambda T: _st2(T)["contact"]["sun-planet"]["S_H"], SH_MIN),
    "contact_planet_ring (S_H=1.2)": solve_T2(lambda T: _st2(T)["contact"]["planet-ring"]["S_H_ring"], SH_MIN),
    "bending_planet (S_F=1.5)": solve_T2(lambda T: _st2(T)["bending"]["planet"]["S_F"], SF_MIN),
    "planet_bearing (L10h=10000 h)": solve_T2(
        lambda T: planet_bearing(T / I_STAGE, MOTOR["n_rated"] / I_STAGE)["L10h"], L_H),
}
def _SH_stage2_methodC(T2):
    """Stage 2 S_H with K_H_beta from the misalignment budget (M6 pin fit, uncrowned flanks)."""
    global KHB, KFB
    T_sun, n_sun = T2 / I_STAGE, MOTOR["n_rated"] / I_STAGE
    r = check_stage(T_sun, n_sun, K_A)
    Fbx = math.hypot(f_Hbeta(d(zp), b), (7 / 2) / PIN_SPAN["stage2"] * b)
    keep = (KHB, KFB)
    KHB = KHB_methodC(r["Ft_per_mesh"] * K_A * r["Kv"] / b, Fbx); KFB = KHB ** NF_exp
    rr = check_stage(T_sun, n_sun, K_A)
    KHB, KFB = keep
    return min(rr["contact"]["sun-planet"]["S_H"], rr["contact"]["planet-ring"]["S_H_ring"])
rating["contact, K_Hbeta method C, uncrowned (S_H=1.2)"] = solve_T2(_SH_stage2_methodC, SH_MIN)
rating["governing"] = min(rating, key=rating.get)

# Material comparison for the most loaded flank (stage 2 sun, nominal fatigue case)
def SH_with(mat_name):
    global SUN_PLANET_MAT
    keep = SUN_PLANET_MAT
    SUN_PLANET_MAT = mat_name
    r = check_stage(MOTOR["T_rated"] * I_STAGE, MOTOR["n_rated"] / I_STAGE, K_A)["contact"]["sun-planet"]["S_H"]
    SUN_PLANET_MAT = keep
    return r
material_comparison = {k: SH_with(k) for k in MAT}

results = dict(
    rating_T2N_max=rating,
    material_comparison_SH_sun_stage2=material_comparison,
    motor=MOTOR, i_stage=I_STAGE, i_total=I_TOTAL, T2N=T2N, T2B=T2B,
    T2N_with_eta=MOTOR["T_rated"] * I_TOTAL * eta_stage**2,
    n_out=MOTOR["n_rated"] / I_TOTAL,
    geometry=dict(a_w=a_w, z_min_undercut=z_min_undercut, eps_sun_planet=eps_sp, eps_planet_ring=eps_pr,
                  d_sun=d(zs), d_planet=d(zp), d_ring=d(zr), ring_root_d=m * (zr + 2.5),
                  planet_root_d=m * (zp - 2.5), assembly_check=(zs + zr) / N_PL),
    factors=dict(ZH=ZH, ZE=ZE, KHB=KHB, KFB=KFB, K_A=K_A, K_gamma=K_GAMMA),
    efficiency=dict(mu=MU, eta_sp=eta_sp, eta_pr=eta_pr, eta0=eta0, eta_stage_mesh=eta_stage_mesh,
                    eta_stage=eta_stage, eta_total=eta_stage**2),
    cases=cases,
    planet_bearing={
        "stage1": planet_bearing(MOTOR["T_rated"], MOTOR["n_rated"]),
        "stage2": planet_bearing(MOTOR["T_rated"] * I_STAGE, MOTOR["n_rated"] / I_STAGE),
        "stage2_static": planet_bearing(MOTOR["T_peak"] * I_STAGE, 0, static=True),
    },
    planet_pin_stage1_peak=planet_pin(MOTOR["T_peak"], PIN_SPAN["stage1"]),
    planet_pin_stage2_peak=planet_pin(MOTOR["T_peak"] * I_STAGE, PIN_SPAN["stage2"]),
    planets=PLANETS,
    materials=dict(sun_planet=SUN_PLANET_MAT, ring=RING_MAT, values=MAT, pin=PIN_MAT, shaft=SHAFT_MAT,
                   thrust_washer=WASHER["mat"]),
    output=dict(bearing=TRB, pressure_centre_offset=PC_OFFSET, L_span=L_SPAN, x_overhang=X_OVER,
                F2r_limits=F2R_LIMITS, F2r_rated=F2R_RATED, F2a_rated=F2A_RATED, M2k_Nm=M2K,
                rated_check=OUTPUT_RATED, sigma_N=SIGMA_N),
    input=dict(bearing=DGBB, F_radial_assumed=F_IN_RADIAL, **input_check()),
    fits=FITS_OUT,
    carriers=CARRIER,
    housing=HOUSING,
    step8=STEP8,
)

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "02_design_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(json.dumps(results, indent=2, ensure_ascii=False))
