# qgis_geochem_plots
 WAXI geochem plotting utilities

This script creates:
1. Chondrite-or Primitive Mantle normalized spider diagrams (REE + trace elements)
2. Tectonic discrimination diagrams:
   - Nb/Y vs Zr/Ti (Winchester & Floyd 1977; Pearce 1996)
   - Zr/4-2Nb-Y ternary (Meschede 1986)
   - Nb vs Y (Pearce et al. 1984)
   - Rb vs (Y+Nb) (Pearce et al. 1984)
   - Ti vs Zr (Pearce & Cann 1973)

## Usage:
    1. Open QGIS and load your vector point layer with geochemical data
    2. Select some or all of the points (can be updated in dialog)
    3. Open the Python Console (Plugins > Python Console)
    4. Load this script and run it
    5. A dialog will appear to select your layer and configure plots

![pics](Montage.png)  