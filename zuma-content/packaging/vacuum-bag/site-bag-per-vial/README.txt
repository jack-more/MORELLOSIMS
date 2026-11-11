One vial centred in the approved blue bag (100 x 150 mm), one image per product, for the site Bag view.

True-blue version (11 Nov 2026): matched to the front print plate (supplier-pack-blue/print/front-blue-proof.jpg, film blue #62B8E1, hue 199).
The first renders came out grey-teal (saturation 27% against the plate's 68%): the film shader's frost and gloss and the AgX view mute the ink.
Fix: a denser ink texture (tinted/source/front-tint-blue-dense.png = the blue Lightbox tint ^1.7), EXPOSURE=0.3, then
tinted/source/grade.py raw.png out.png 1.45 0.147, which moves only blue film pixels to the plate's hue, saturation and lightness.
Render: tinted/source/bag4.py with EXPOSURE=0.3 PW=10 PH=15 CLENS=70 SPACING=0.035 TENT=1.0 FREE=0.6 TPOW=2.4 CW=0.16 GLINT=0.35
TINTFROST=0.08 COAT=0.15 VY=1.0 VIALS=NN@1.1, TINTART = front-tint-blue-dense.png, BACKART = palm shadow, 720 x 960, 40 samples.

Palm back plate (11 Nov 2026): the back sheet's palm shadow was too faint to read through the blue. Renders now use
tinted/source/back-sheet-shadow-dense.png (the palm plate ^1.8, darkest 16% instead of 37%) and tinted/source/grade.py, which recolours the
blue film to the plate blue at each pixel's own brightness, so the palm stays dark, glints stay white and the white ink is untouched.
