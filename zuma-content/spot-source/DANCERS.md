# Dancer clips (Higgsfield, Kling 3.0 Pro, 5 s, 16:9, no sound)

Keyed to silhouettes with `python3 key.py <clip.mp4> dance/dN`. The keyed frames are in `dance/`; the raw clips are not in git.
Re-download a raw clip from the Higgsfield library by its job ID.

| Clip | Look | Colour | Job ID |
|---|---|---|---|
| d0 | Hoodie, hip-hop | Blue | 399425a7-4133-40ac-8e39-ea374f7a6283 |
| d1 | Hoodie, take 2 | Blue | 75b91aee-c58e-43d3-86f9-3d1face25317 |
| d2 | Ponytail, pop | Green | 56553910-24f8-4a64-baae-b1b72a3852d7 |
| d3 | Ponytail, take 2 | Green | ffc7085b-4d37-4f67-a86c-485a62f9b67a |
| d4 | Cap, toprock | Orange | 194db974-463e-4849-a26a-da16066a6353 |
| d5 | Cap, take 2 | Orange | 873bc4d8-4b36-44fe-bd0d-4b9df8e4e494 |
| d6 | Afro puff, house | Amber | 1867ae38-f5d0-4fb8-86f5-1dad79a1bac2 |
| d7 | Afro puff, take 2 | Amber | 8fae2bab-db36-4f73-a332-56170de44c81 |
| d8 | Suit, funk | Violet | 5d532962-582e-43ec-9096-032f5944fe8a |
| d9 | Suit, take 2 | Violet | 48153539-85cb-4e07-aef9-4613b7609f0c |

Cost: 10 clips x 7.5 credits = 75 credits.

Render: serve the scratch folder on port 8772, then `node shoot.cjs 30 0 23.5` and
`ffmpeg -framerate 30 -i frames/%05d.jpg -i music.wav -c:v libx264 -crf 17 -pix_fmt yuv420p -c:a aac -shortest zuma-spot-dancers.mp4`.
