
import os
import board
import digitalio
import busio
import time
import random


from displayio import OnDiskBitmap, TileGrid, Group
main_group = Group()
blinka_img = OnDiskBitmap("images/penguin.bmp")
tile_grid = TileGrid(bitmap=blinka_img, pixel_shader=blinka_img.pixel_shader)
main_group.append(tile_grid)
board.DISPLAY.show(main_group)
tile_grid.x = board.DISPLAY.width // 2 - blinka_img.width // 2


