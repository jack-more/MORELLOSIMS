# Launch video: "It's a new era of research, here now."

- `zuma-launch-new-era.mp4`: 9:16, 1080 x 1920, about 18 s with sound. 15 s film plus the end card.
- Film: Higgsfield Seedance 2.5 (omni reference), from three of our own images: the RT-3 vial render, the blue one-box render (`packaging/one-box/factory-blue/box-blue-look.png`) and the blue Lightbox still (`brand/lightbox-3d/`).
- End card (`endcard.png`): set by us in Outfit, ZUMA blue #1E74A8, Snow #FCFBF8, Oxblood #6E1C2A band with the research-use line. AI video garbles type, so no words come from the model.

## Montage cut (10 Nov 2026), the one to post
- `zuma-launch-montage.mp4`: 9:16, 1080 x 1920, about 18 s with sound. Fast cuts in the style of the reference launch post: archival lab, pipette drop, the blue Lightbox glass, the RT-3 vial, rocket, city, vials, Earth at sunrise, RT-3 hero. No box.
- Footage: `footage-montage-raw.mp4`, Higgsfield Seedance 2.5 at 720p (no text in the footage), from the RT-3 vial render and the blue Lightbox still.
- Captions and end card added in post by `source/edit.py` (white pills typed a word at a time in Outfit, timed to the cuts; end card on ZUMA blue with the research-use line). Edit the LINES list and rerun to change the words.

## Our-assets cut (10 Nov 2026): zuma-launch-cut.mp4
- 9:16, 1080 x 1920, 25 s, 83 cuts at 128 BPM (on the beat, half beat and quarter beat). Zero AI credits.
- Built only from our own material: the six Lightboxes (ombre.js, bars + palm, `source/lightbox/`), the site's vial renders and turntable frames (front arc only, so no old QR shows),
  the Rev 4 label print art, the blue vacuum bag renders, mailer B, the round stickers. No box.
- Words: "It's a new era / of research." · big "Tested / by / lot." · "Every lot. Every report." · "Vacuum packed." · "Sealed. Shipped." · big "here / now." · crest turn with zumatides.com typed · end card with the research-use line.
- The music is synthesised in the script (128 BPM kick, clap, hats, sub bass, riser, impact). Swap in a licensed track on the platform if you like; the cuts sit on 128 BPM.
- Rebuild: `python source/cut.py <dir with lb-*.png> out.mp4`. Edit SHOTS/CAPS in the script to change shots or words.
