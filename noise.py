# used to generate data for rain animation
# from noise import Noise
# noise = Noise().get(channels=17, steps=200)
# then paste into animations.py as static data

from perlin_noise import PerlinNoise


class Noise():
    def get(self, channels = 10, steps = 100):
        noise1 = PerlinNoise(octaves=3)
        noise2 = PerlinNoise(octaves=6)
        noise3 = PerlinNoise(octaves=12)
        noise4 = PerlinNoise(octaves=24)

        xpix, ypix = steps, channels
        sequence = []
        for i in range(xpix):
            row = []
            for j in range(ypix):
                noise_val = noise1([i/xpix, j/ypix])
                noise_val += 0.5 * noise2([i/xpix, j/ypix])
                noise_val += 0.25 * noise3([i/xpix, j/ypix])
                noise_val += 0.125 * noise4([i/xpix, j/ypix])

                row.append(noise_val)
            sequence.append(row)

        # print min and max values across all rows of sequence
        min_val = min([min(row) for row in sequence])
        max_val = max([max(row) for row in sequence])
        print(min_val, max_val)
        # scale entire sequence to [0, 255]
        sequence = [[int((val - min_val) / (max_val - min_val) * 4095) for val in row] for row in sequence]

        return sequence