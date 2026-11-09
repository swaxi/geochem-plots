"""
Geochemistry Plotting Tools - REE Shape Coefficients
====================================================
REE pattern shape coefficients (lambda0 to lambda4) of O'Neill (2016):

    ln([REE]/[REE]CI) = l0 + l1*f1(r) + l2*f2(r) + l3*f3(r) + l4*f4(r)

where r is the REE3+ ionic radius in eight-fold coordination (Shannon,
1976) and f1..f4 are the orthogonal polynomials of O'Neill (2016) Table 2,
built for the 13 REE without Eu. lambda0 is the average of ln([REE]/[REE]CI),
lambda1 the linear slope (positive for LREE-enriched patterns), lambda2
the quadratic curvature, lambda3 the sigmoidal deviation and lambda4 the
W/M-shaped term.

All the reference data are taken from the paper: ionic radii and CI
chondrite abundances from Table 1, orthogonal polynomials from Table 2.
Eu is never used in the fit. The polynomials are kept the same whatever
REE are missing, as O'Neill (2016) recommends, so that the coefficients
stay comparable between samples; the fit is an ordinary least-squares
fit with equal weights on ln([REE]/[REE]CI) (the same algebra as
pyrolite's lambdas_ONeill2016).

O'Neill, H. St. C. (2016). The Smoothness and Shapes of Chondrite-normalized
Rare Earth Element Patterns in Basalts. Journal of Petrology 57, 1463-1508.
doi:10.1093/petrology/egw047

Pure Python + numpy (no QGIS), so it can be unit tested on its own.
"""

import math

import numpy as np

REFERENCE = "O'Neill (2016)"

# Table 1: REE3+ ionic radii in eight-fold coordination (Shannon, 1976), in
# Angstrom (pm/100).
ONEILL_2016_RADII = {
    'La': 1.160, 'Ce': 1.143, 'Pr': 1.126, 'Nd': 1.109, 'Sm': 1.079,
    'Eu': 1.066, 'Gd': 1.053, 'Tb': 1.040, 'Dy': 1.027, 'Ho': 1.015,
    'Er': 1.004, 'Tm': 0.994, 'Yb': 0.985, 'Lu': 0.977,
}

# Table 1: CI chondrite abundances, in ug/g (= ppm).
ONEILL_2016_CI_CHONDRITE = {
    'La': 0.2472, 'Ce': 0.6308, 'Pr': 0.0950, 'Nd': 0.4793, 'Sm': 0.1542,
    'Eu': 0.0592, 'Gd': 0.2059, 'Tb': 0.0375, 'Dy': 0.2540, 'Ho': 0.0554,
    'Er': 0.1645, 'Tm': 0.0258, 'Yb': 0.1684, 'Lu': 0.0251,
}

# Table 2: roots of the orthogonal polynomials f0..f4, e.g.
# f2 = (r - 1.00533) * (r - 1.12824). f0 = 1.
ONEILL_2016_ORTHOGONAL_ROOTS = (
    (),
    (1.05477,),
    (1.00533, 1.12824),
    (0.99141, 1.06055, 1.14552),
    (0.98482, 1.03052, 1.10441, 1.15343),
)

# REE used in the fit: all 14 except Eu (anomalous, Eu2+).
FIT_ELEMENTS = ('La', 'Ce', 'Pr', 'Nd', 'Sm', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu')
LREE_END = ('La', 'Ce', 'Pr', 'Nd')
HREE_END = ('Er', 'Tm', 'Yb', 'Lu')

N_COEFFICIENTS = len(ONEILL_2016_ORTHOGONAL_ROOTS)
# One more REE than coefficients, so the fit is not just an exact
# interpolation through the data points.
MIN_FIT_ELEMENTS = N_COEFFICIENTS + 1

FIELD_NAMES = tuple(f'lambda{n}' for n in range(N_COEFFICIENTS))


def orthogonal_terms(radius):
    """Values of f0..f4 (O'Neill 2016, Table 2) at ionic radius `radius`."""
    return [math.prod(radius - root for root in roots)
            for roots in ONEILL_2016_ORTHOGONAL_ROOTS]


def usable_fit_elements(concentrations):
    """The fit elements (no Eu) with a finite, positive concentration."""
    usable = []
    for element in FIT_ELEMENTS:
        value = concentrations.get(element)
        if value is not None and math.isfinite(value) and value > 0:
            usable.append(element)
    return usable


def missing_data_reason(usable):
    """Why the REE in `usable` can't define the pattern shape, or None if
    they can: at least MIN_FIT_ELEMENTS REE (Eu excluded), including at
    least one LREE (La-Nd) and one HREE (Er-Lu), since the shape is not
    defined if a whole end of the pattern is missing."""
    if len(usable) < MIN_FIT_ELEMENTS:
        return (f"only {len(usable)} REE (Eu excluded) with positive values; "
                f"at least {MIN_FIT_ELEMENTS} are needed")
    if not any(e in usable for e in LREE_END):
        return "no LREE (La, Ce, Pr or Nd)"
    if not any(e in usable for e in HREE_END):
        return "no HREE (Er, Tm, Yb or Lu)"
    return None


def fit_lambdas(concentrations):
    """Shape coefficients of one sample.

    `concentrations` maps REE symbols to concentrations in ppm (missing,
    None, zero or negative values are ignored; Eu is ignored).

    Returns (lambdas, None), with lambdas the list [lambda0, ..., lambda4],
    or (None, reason) when the available REE can't define the pattern.
    """
    usable = usable_fit_elements(concentrations)
    reason = missing_data_reason(usable)
    if reason is not None:
        return None, reason
    design = np.array([orthogonal_terms(ONEILL_2016_RADII[e]) for e in usable])
    ln_normalised = np.array([math.log(concentrations[e] / ONEILL_2016_CI_CHONDRITE[e])
                              for e in usable])
    coefficients, *_ = np.linalg.lstsq(design, ln_normalised, rcond=None)
    return [float(c) for c in coefficients], None
